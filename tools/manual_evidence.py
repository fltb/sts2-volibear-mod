"""Independent ordinary-input/payment gate. Never accepts a probe's passed boolean."""
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

READY_PREFIX = '[Volibear] MANUAL_PLAY_READY '
RESULT_PREFIX = '[Volibear] MANUAL_PLAY_RESULT '
MOVE_FLAGS = 0xC001  # MOVE | ABSOLUTE | VIRTUALDESK
STEPS = 24


class EvidenceError(ValueError):
    pass


def require(condition, label):
    if not condition:
        raise EvidenceError(label)


def exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(exact(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def integer(value):
    return type(value) is int


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def point(value):
    return (isinstance(value, list) and len(value) == 2
            and all(numeric(number) for number in value))


def rounded(value):
    require(point(value), 'invalid point')
    return [round(value[0]), round(value[1])]


def one_record(log, prefix):
    records = [json.loads(line[len(prefix):]) for line in log.splitlines() if line.startswith(prefix)]
    require(len(records) == 1 and isinstance(records[0], dict), 'missing/duplicate marker: ' + prefix)
    return records[0]


def validate_ready(ready, token, nonce, pid):
    expected = dict(schema=1, token=token, nonce=nonce, scenario='manual-play', variant='b01',
                    gameVersion='v0.107.1', gameCommit='59260271', os='Windows',
                    processId=pid, godotProcessId=pid, pidSource='System.Environment.ProcessId',
                    testMode=False, steamInitialized=False, encounter='SlimesWeak')
    for key, value in expected.items():
        require(type(ready.get(key)) is type(value) and ready[key] == value, 'ready.' + key)
    require(integer(pid) and pid > 0 and len(nonce) == 48, 'owned identity')
    require(ready['display'] != 'headless' and bool(ready['display']), 'native display')
    window = ready['window']
    require(integer(window['hwnd']) and window['hwnd'] > 0, 'native HWND')
    require(point(window['position']) and point(window['size']) and point(window['viewportSize']), 'window geometry')
    require(all(integer(n) for n in window['size']) and min(window['size']) >= 360, 'window size')
    matrix = window['screenTransform']
    require(isinstance(matrix, list) and len(matrix) == 3 and all(point(p) for p in matrix), 'viewport transform')
    for key in ('card', 'target'):
        anchor = ready['anchors'][key]
        require(integer(anchor['nodeId']) and anchor['nodeId'] > 0, 'native anchor identity')
        require(point(anchor['local']) and point(anchor['viewport']) and point(anchor['screen']), 'native anchor points')
        x, y = anchor['viewport']
        expected_screen = [matrix[0][i] * x + matrix[1][i] * y + matrix[2][i] for i in range(2)]
        require(all(abs(a - b) <= 1 for a, b in zip(expected_screen, anchor['screen'])), 'anchor transform mismatch')
        require(0 <= x < window['viewportSize'][0] and 0 <= y < window['viewportSize'][1], 'anchor outside viewport')
    require(integer(ready['readyTickMs']) and ready['readyTickMs'] > 0, 'ready clock')
    require(ready['fixtureApi'] == 'CardPileCmd.Add;CreatureCmd.SetMaxAndCurrentHp', 'fixture boundary')


def validate_png(content, width, height):
    """Validate a complete Godot RGB/RGBA8 PNG, not merely its signature or header."""
    require(isinstance(content, bytes) and 8 < len(content) <= 64 * 1024 * 1024, 'PNG file size')
    require(content[:8] == b'\x89PNG\r\n\x1a\n', 'PNG signature')
    require(integer(width) and integer(height) and 640 <= width <= 8192 and 360 <= height <= 8192
            and width * height <= 33554432, 'viewport image dimensions')
    position, channels = 8, None
    chunks, compressed = [], []
    idat_finished, ended = False, False
    while position < len(content):
        require(position + 12 <= len(content), 'truncated PNG chunk')
        length = struct.unpack_from('>I', content, position)[0]
        name = content[position+4:position+8]
        finish = position + 12 + length
        require(length <= 0x7fffffff and finish <= len(content), 'PNG chunk bounds')
        require(all(65 <= c <= 90 or 97 <= c <= 122 for c in name) and 65 <= name[2] <= 90, 'PNG chunk name')
        payload = content[position+8:position+8+length]
        crc = struct.unpack_from('>I', content, position+8+length)[0]
        require((zlib.crc32(name + payload) & 0xffffffff) == crc, 'PNG chunk CRC')
        require(chunks or name == b'IHDR', 'PNG must begin with IHDR')
        if name == b'IHDR':
            require(not chunks and length == 13, 'duplicate/invalid PNG IHDR')
            actual_width, actual_height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            require((actual_width, actual_height) == (width, height), 'actual PNG dimensions')
            require(depth == 8 and color in (2, 6) and compression == filtering == interlace == 0,
                    'PNG must be supported RGB/RGBA8 noninterlaced')
            channels = 3 if color == 2 else 4
        elif name == b'PLTE':
            require(b'PLTE' not in chunks and not compressed and 3 <= length <= 768 and length % 3 == 0, 'invalid PNG palette')
        elif name == b'IDAT':
            require(channels is not None and not idat_finished, 'noncontiguous PNG image data')
            compressed.append(payload)
        elif name == b'IEND':
            require(length == 0 and bool(compressed) and finish == len(content), 'invalid/missing/trailing PNG end')
            ended = True
        else:
            require(name[0] & 32, 'unknown critical PNG chunk')
        if compressed and name != b'IDAT':
            idat_finished = True
        chunks.append(name)
        position = finish
    require(ended and chunks[-1] == b'IEND' and channels is not None, 'incomplete PNG')
    row_size = width * channels + 1
    expected = row_size * height
    decoder = zlib.decompressobj()
    try:
        pixels = decoder.decompress(b''.join(compressed), expected + 1)
    except zlib.error as error:
        raise EvidenceError('invalid PNG zlib stream') from error
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail, 'incomplete/trailing PNG zlib stream')
    require(len(pixels) == expected, 'PNG decompressed scanline length')
    require(all(pixels[offset] in (0, 1, 2, 3, 4) for offset in range(0, expected, row_size)), 'invalid PNG scanline filter')
    return hashlib.sha256(content).hexdigest()


def validate_activation(ready, injected, pid, activate_owned_window):
    require(type(activate_owned_window) is bool, 'trusted activation option must be boolean')
    activation = injected.get('activation')
    if not activate_owned_window:
        require(activation is None, 'focus request without trusted CLI opt-in')
        return
    require(isinstance(activation, dict), 'missing opt-in activation receipt')
    require(activation['requested'] is True and activation['requestResult'] is True and
            activation['jobMember'] is True and activation['pressedButtons'] == [], 'activation preflight/result')
    require(integer(activation['requestCount']) and activation['requestCount'] == 1, 'exactly one activation request')
    for key in ('targetHwnd','targetPid','jobHandle','oldForegroundHwnd','oldForegroundPid',
                'postForegroundHwnd','postForegroundPid','launchTickMs','launchLastInputTickMs',
                'checkTickMs','lastInputTickMs','requestTickMs','postTickMs','postLastInputTickMs'):
        require(integer(activation[key]) and activation[key] >= 0, 'activation integer: ' + key)
    hwnd = ready['window']['hwnd']
    require(activation['targetHwnd'] == activation['postForegroundHwnd'] == hwnd and
            activation['targetPid'] == activation['postForegroundPid'] == pid and
            activation['jobHandle'] == injected['spawn']['jobHandle'], 'activation actual owned identity')
    require((activation['oldForegroundHwnd'] == 0) == (activation['oldForegroundPid'] == 0), 'previous foreground identity')
    if activation['oldForegroundHwnd'] == hwnd:
        require(activation['oldForegroundPid'] == pid, 'previous owned foreground PID')
    require(integer(injected['spawn']['launchTickMs']) and integer(injected['spawn']['launchLastInputTickMs']),
            'spawn activation clocks must be integers')
    require(activation['launchTickMs'] == injected['spawn']['launchTickMs'] and
            activation['launchLastInputTickMs'] == injected['spawn']['launchLastInputTickMs'], 'actual spawn clock binding')
    baseline = activation['launchLastInputTickMs']
    require(baseline == activation['lastInputTickMs'] == activation['postLastInputTickMs'] < activation['launchTickMs'],
            'user input since pre-launch baseline')
    require(activation['launchTickMs'] <= ready['readyTickMs'] <= activation['checkTickMs'] <=
            activation['requestTickMs'] <= activation['postTickMs'] <= injected['packets'][0]['tickMs'],
            'activation/ready/input clock ordering')


def _validate(ready, result, injected, token, nonce, pid, directory, activate_owned_window):
    validate_ready(ready, token, nonce, pid)
    for record in (result, injected):
        for key, value in dict(schema=1, token=token, nonce=nonce, processId=pid).items():
            require(type(record.get(key)) is type(value) and record[key] == value, 'result/input identity: ' + key)
    require(result['scenario'] == 'manual-play' and result['variant'] == 'b01', 'result scenario')
    require(result['gameVersion'] == 'v0.107.1' and result['gameCommit'] == '59260271', 'result version')
    require(result['api'] == injected['api'] == 'Windows.SendInput.mouse_drag', 'real input API')
    require(result['acceptance'] == 'ordinary-input-and-native-payment', 'acceptance scope')
    require(injected['error'] is None, 'injection error')
    require(injected['spawn']['pid'] == pid and integer(injected['spawn']['jobHandle'])
            and injected['spawn']['jobHandle'] > 0, 'owned spawned Windows job')
    hwnd = ready['window']['hwnd']
    require(injected['hwnd'] == hwnd, 'input HWND')
    packets = injected['packets']
    require(isinstance(packets, list) and bool(packets), 'missing input packets')
    validate_activation(ready, injected, pid, activate_owned_window)
    kinds = ['move', 'down'] + ['move'] * STEPS + ['up']
    require([p['kind'] for p in packets] == kinds, 'exact single mouse drag; no extra input')
    start, end = (rounded(ready['anchors'][key]['screen']) for key in ('card', 'target'))
    expected_points = [start, start] + [[round(start[i] + (end[i] - start[i]) * step / STEPS)
                                       for i in range(2)] for step in range(1, STEPS + 1)] + [end]
    ticks = []
    for packet, expected_point in zip(packets, expected_points):
        require(packet['point'] == expected_point, 'drag coordinates')
        require(packet['sent'] == 1 and type(packet['sent']) is int, 'SendInput did not insert packet')
        require(packet['foregroundHwnd'] == packet['pointHwnd'] == hwnd and packet['foregroundPid'] == pid,
                'foreign foreground/point owner')
        require(packet['flags'] == {'move': MOVE_FLAGS, 'down': 2, 'up': 4}[packet['kind']], 'mouse-only flags')
        vx, vy, vw, vh = packet['virtualScreen']
        require(all(integer(n) for n in packet['virtualScreen']) and vw > 1 and vh > 1, 'virtual desktop geometry')
        require(packet['normalised'] == [round((expected_point[0]-vx)*65535/(vw-1)),
                                        round((expected_point[1]-vy)*65535/(vh-1))], 'actual absolute mouse coordinates')
        require(point(packet['cursor']) and all(abs(a-b) <= 2 for a, b in zip(packet['cursor'], expected_point)),
                'cursor not at submitted coordinate')
        left, top, width, height = packet['clientRect']
        ox, oy, ow, oh = packet['outerRect']
        require(all(integer(n) for n in packet['clientRect'] + packet['outerRect']) and
                ox <= left and oy <= top and ox+ow >= left+width and oy+oh >= top+height, 'physical window bounds')
        require(any(all(abs(a-b) <= 2 for a,b in zip(ready['window']['position'], origin))
                    for origin in ([left,top],[ox,oy])), 'native/Win32 window position mismatch')
        require([width, height] == ready['window']['size'], 'resized client')
        require(left <= expected_point[0] < left + width and top <= expected_point[1] < top + height,
                'point outside owned client')
        require(integer(packet['tickMs']) and packet['tickMs'] >= ready['readyTickMs'], 'input clock')
        ticks.append(packet['tickMs'])
    require(ticks == sorted(ticks) and ticks[0] - ready['readyTickMs'] <= 10000, 'stale/unordered input')
    require(100 <= ticks[-1] - ticks[1] <= 3000, 'drag duration')
    require(all(p['clientRect'] == packets[0]['clientRect'] for p in packets), 'moved window during drag')
    before, after = result['before'], result['after']
    require(before == ready['before'], 'before snapshot mismatch')
    card_id, target_id = ready['cardId'], ready['targetId']
    require(integer(card_id) and integer(target_id), 'native entity IDs')
    for snapshot in (before, after):
        require(snapshot['cardId'] == card_id and snapshot['cardModel'] == snapshot['masterModel'] == 'Volibear_B01', 'original B01 identity')
        require(snapshot['upgraded'] is False and integer(snapshot['masterIndex']) and 0 <= snapshot['masterIndex'] < 10, 'unupgraded master-backed card')
        require(snapshot['round'] == snapshot['turn'] == 1 and snapshot['phase'] == 'Play', 'same ordinary player turn')
        require(snapshot['maxEnergy'] == 3 and snapshot['playerHp'] == 80 and snapshot['playerBlock'] == 0, 'fresh player fixture')
        require(snapshot['actionsDisabled'] is False and snapshot['executingCard'] is False, 'settled playable state')
        require(len(snapshot['deck']) == 10, 'native deck size')
    require(before['masterIndex'] == after['masterIndex'] and before['deck'] == after['deck'], 'master deck changed')
    require(before['playerId'] == after['playerId'] and before['playerNetId'] == after['playerNetId'], 'player identity changed')
    require(before['energy'] == 3 and after['energy'] == 2, 'native energy 3->2')
    require(before['pile'] == 'Hand' and after['pile'] == 'Discard', 'same card Hand->Discard')
    require(before['piles']['Hand'] == [card_id] and after['piles']['Hand'] == [], 'single-card hand transition')
    require(card_id not in before['piles']['Discard'] and
            sorted(after['piles']['Discard']) == sorted(before['piles']['Discard'] + [card_id]), 'discard entity preservation')
    originals = ready['originalCardIds']
    require(len(originals) == len(set(originals)) == 10 and card_id in originals, 'original combat deck identities')
    for snapshot in (before, after):
        require(sorted(x for pile in snapshot['piles'].values() for x in pile) == sorted(originals), 'lost/replaced/generated combat card')
    for pile in set(before['piles']) - {'Hand', 'Discard'}:
        require(before['piles'][pile] == after['piles'][pile], 'unrelated pile changed')
    require(len(before['enemies']) == len(after['enemies']) == 3, 'native three-enemy fixture')
    require(len({e['id'] for e in before['enemies']}) == 3 and target_id in [e['id'] for e in before['enemies']], 'target membership')
    for old, new in zip(before['enemies'], after['enemies']):
        require(old['id'] == new['id'] and old['model'] == new['model'] and bool(old['model']), 'enemy identity changed')
        require(old['hp'] == old['maxHp'] == new['maxHp'] == 50 and old['block'] == new['block'] == 0, 'HP50 unblocked fixture')
        require(new['hp'] == (44 if old['id'] == target_id else 50), 'actual target HP50->44 only')
    history = result['history']
    def only(kind):
        rows = [row for row in history if row['kind'] == kind]
        require(len(rows) == 1, 'exact native history count: ' + kind)
        return rows[0]
    energy, started, finished = (only(kind) for kind in ('EnergySpentEntry', 'CardPlayStartedEntry', 'CardPlayFinishedEntry'))
    require(exact(energy['data'], {'amount': 1, 'playerId': before['playerId']}), 'actual native EnergySpentEntry')
    expected_play = dict(cardId=card_id, cardModel='Volibear_B01', targetId=target_id,
                         isAutoPlay=False, energySpent=1, energyValue=1, starsSpent=0,
                         playIndex=0, playCount=1, resultPile='Discard')
    for row in (started, finished):
        require(exact(row['data'], expected_play), 'native non-AutoPlay resource receipt')
    require(energy['index'] < started['index'] < finished['index'], 'native payment/play order')
    require(ticks[-1] <= energy['tickMs'] <= started['tickMs'] <= finished['tickMs'] <= ticks[-1] + 15000,
            'native play did not follow the owned mouse-up')
    attack, damage = only('CreatureAttackedEntry'), only('DamageReceivedEntry')
    expected_hit = dict(targetId=target_id, unblocked=6, blocked=0, overkill=0, killed=False)
    require(exact(attack['data'], {'attackerId': before['playerId'], 'hits': [expected_hit]}), 'actual native attack receipt')
    require(exact(damage['data'], {'receiverId': target_id, 'cardId': card_id, 'hit': expected_hit}), 'actual native damage receipt')
    require(started['index'] < damage['index'] < attack['index'] < finished['index'], 'damage inside actual play')
    require(ready['beforeCapture'] == result['beforeCapture'], 'before capture provenance')
    if directory is not None:
        digests = []
        for key, filename in (('beforeCapture', 'manual-before.png'), ('afterCapture', 'manual-after.png')):
            capture = result[key]
            require(capture['file'] == filename and capture['source'] == 'NGame.GetViewport.GetTexture.GetImage', 'viewport capture source')
            path = Path(directory) / filename
            digests.append(validate_png(path.read_bytes(), capture['width'], capture['height']))
        require(digests[0] != digests[1], 'before/after image reused')


def check_log(log, ready, injected, token, nonce, pid, directory=None, *, activate_owned_window=False):
    try:
        require('MANUAL_PLAY_ERROR' not in log, 'probe error marker')
        require(one_record(log, READY_PREFIX) == ready, 'ready file/log mismatch')
        result = one_record(log, RESULT_PREFIX)
        _validate(ready, result, injected, token, nonce, pid, directory, activate_owned_window)
        return {'valid': True, 'error': None, 'result': result}
    except (EvidenceError, KeyError, TypeError, ValueError, OSError, AttributeError) as error:
        return {'valid': False, 'error': str(error), 'result': None}
