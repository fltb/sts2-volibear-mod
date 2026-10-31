extends Node2D
## Standalone Godot 4.5.1 asset playback; no game DLL, model registration or combat logic.

var asset_root: String
var animation_manifest: Dictionary = {}
var animation_items: Array = []
var effect_items: Array = []
var audio_items: Array = []
var character := AnimatedSprite2D.new()
var effects: Array[AnimatedSprite2D] = []
var effect_loops: Dictionary = {}
var audio_players: Array[AudioStreamPlayer] = []
var audio_loops: Dictionary = {}
var last_audio_ms: Dictionary = {}
var action_picker := OptionButton.new()
var effect_picker := OptionButton.new()
var audio_picker := OptionButton.new()
var status := Label.new()
var self_test := false
var failure_messages: Array[String] = []
var texture_cache: Dictionary = {}
var animation_folder: String
var input_hashes: Dictionary = {}
var action_cues: Dictionary = {}
var pending_action_events: Array = []
var pending_action_next := 0
var active_action := ""
var sync_enabled := true

func _ready() -> void:
    asset_root = ProjectSettings.globalize_path("res://").path_join("..").simplify_path()
    if FileAccess.file_exists("res://VolibearArt/animations/manifest.json"):
        asset_root = "res://VolibearArt"
    self_test = "--self-test" in OS.get_cmdline_user_args()
    animation_folder = asset_root.path_join("animations/clean")
    if not FileAccess.file_exists(animation_folder.path_join("manifest.json")):
        animation_folder = asset_root.path_join("animations")
    animation_manifest = read_json(animation_folder.path_join("manifest.json"))
    input_hashes[animation_folder.path_join("manifest.json")] = FileAccess.get_sha256(animation_folder.path_join("manifest.json"))
    animation_items = animation_manifest.get("clips", []) + animation_manifest.get("variants", [])
    var vfx_path: String = asset_root.path_join("vfx/manifest.json")
    if FileAccess.file_exists(vfx_path):
        effect_items = read_json(vfx_path).get("effects", [])
        input_hashes[vfx_path] = FileAccess.get_sha256(vfx_path)
    var audio_path: String = asset_root.path_join("audio/manifest.json")
    if FileAccess.file_exists(audio_path):
        audio_items = read_json(audio_path).get("cues", [])
        input_hashes[audio_path] = FileAccess.get_sha256(audio_path)
    var cues_path: String=asset_root.path_join("audio/action_cues.json")
    if FileAccess.file_exists(cues_path):
        for row in read_json(cues_path).get("clips",[]):action_cues[str(row["clip"])]=row
        input_hashes[cues_path]=FileAccess.get_sha256(cues_path)
    add_child(character)
    character.position = Vector2(335,625)
    character.centered = false
    character.offset = Vector2(-250,-442)
    character.z_index = 0
    character.animation_finished.connect(func():
        if not active_action.is_empty(): dispatch_action_events(1000000.0))
    if self_test:
        run_self_test.call_deferred()
        return
    build_controls()
    if not animation_items.is_empty():
        play_action(0)

func read_json(path: String) -> Dictionary:
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        record_error("Cannot read " + path)
        return {}
    var parser := JSON.new()
    var result: int = parser.parse(file.get_as_text())
    if result != OK or not parser.data is Dictionary:
        record_error("Invalid JSON " + path)
        return {}
    return parser.data

func record_error(message: String) -> void:
    failure_messages.append(message)
    push_error(message)

func texture_from_path(path: String) -> Texture2D:
    if texture_cache.has(path):
        return texture_cache[path]
    var texture: Texture2D
    if path.begins_with("res://"):
        texture = load(path) as Texture2D
    else:
        var image := Image.new()
        if image.load(path) != OK:
            record_error("Texture cannot be read: " + path)
            return null
        texture = ImageTexture.create_from_image(image)
    if texture == null:
        record_error("Texture missing: " + path)
        return null
    texture_cache[path] = texture
    return texture

func build_frames(item: Dictionary, folder: String, is_character: bool) -> SpriteFrames:
    var name_key: String = "name" if is_character else "id"
    var clip_name: String = str(item.get(name_key,"missing"))
    var atlas: Dictionary = item.get("atlas",{})
    var texture: Texture2D = texture_from_path(folder.path_join(str(atlas.get("image",""))))
    var data: Dictionary = read_json(folder.path_join(str(atlas.get("json","")))) if is_character else item
    var frames: Array = data.get("frames",[])
    var output := SpriteFrames.new()
    output.remove_animation("default")
    output.add_animation(clip_name)
    var fps: float = float(item.get("fps",24.0))
    output.set_animation_speed(clip_name,fps)
    output.set_animation_loop(clip_name,bool(item.get("loop",false)))
    for frame in frames:
        var rect: Array = frame.get("rect",[])
        if rect.size() != 4 or texture == null:
            record_error("Invalid atlas frame " + clip_name)
            continue
        var region := Rect2(float(rect[0]),float(rect[1]),float(rect[2]),float(rect[3]))
        if region.position.x < 0 or region.position.y < 0 or region.end.x > texture.get_width() or region.end.y > texture.get_height():
            record_error("Frame outside atlas " + clip_name)
            continue
        var tile := AtlasTexture.new()
        tile.atlas = texture
        tile.region = region
        tile.filter_clip = true
        var relative_duration: float = float(frame.get("duration_ms",1000.0/fps))*fps/1000.0
        output.add_frame(clip_name,tile,relative_duration)
    if output.get_frame_count(clip_name) != int(item.get("frame_count",-1)):
        record_error("Frame count mismatch " + clip_name)
    return output

func build_controls() -> void:
    var layer := CanvasLayer.new()
    add_child(layer)
    var panel := VBoxContainer.new()
    panel.position = Vector2(30,22)
    panel.size = Vector2(1060,160)
    layer.add_child(panel)
    var title := Label.new()
    title.text = "VOLIBEAR / V5 ART PLAYER"
    title.add_theme_font_size_override("font_size",26)
    panel.add_child(title)
    var note := Label.new()
    note.text = "Native Godot asset proof. Independent animations, VFX and audio. Game integration remains source-only."
    panel.add_child(note)
    var actions := HBoxContainer.new(); panel.add_child(actions)
    action_picker.custom_minimum_size.x = 250
    for item in animation_items: action_picker.add_item(str(item.get("name","")))
    actions.add_child(action_picker)
    add_button(actions,"Play action",func(): play_action(action_picker.selected))
    add_button(actions,"Pause / resume",func():
        if character.is_playing(): character.pause()
        else: character.play())
    add_button(actions,"Stop all loops / FX",stop_all_owned)
    var sync_button:=CheckButton.new()
    sync_button.text="Sync SFX + effects";sync_button.button_pressed=true
    sync_button.toggled.connect(func(on:bool):sync_enabled=on;if not on:stop_all_owned())
    actions.add_child(sync_button)
    var fxrow := HBoxContainer.new(); panel.add_child(fxrow)
    effect_picker.custom_minimum_size.x = 250
    for item in effect_items: effect_picker.add_item(str(item.get("id","")))
    fxrow.add_child(effect_picker)
    add_button(fxrow,"Spawn effect",func(): spawn_effect(effect_picker.selected))
    audio_picker.custom_minimum_size.x = 290
    for item in audio_items: audio_picker.add_item(str(item.get("id","")))
    fxrow.add_child(audio_picker)
    add_button(fxrow,"Play audio",func(): play_audio(audio_picker.selected))
    panel.add_child(status)
    var target := Label.new()
    target.position = Vector2(790,400)
    target.text = "COMBAT TARGET\n(hit / chain)"
    layer.add_child(target)
    var card := Label.new()
    card.position=Vector2(790,675)
    card.text="HAND CARD\n(feral transfer / purify)"
    layer.add_child(card)
    var energy:=Label.new();energy.position=Vector2(45,665);energy.text="ENERGY";layer.add_child(energy)

func add_button(parent: Node,text: String,callback: Callable) -> void:
    var b := Button.new(); b.text=text; b.pressed.connect(callback); parent.add_child(b)

func play_action(index: int) -> void:
    if index < 0 or index >= animation_items.size(): return
    stop_all_owned()
    var item: Dictionary = animation_items[index]
    active_action=str(item["name"])
    character.sprite_frames = build_frames(item,animation_folder,true)
    character.play(str(item["name"]))
    character.set_frame_and_progress(0,0)
    status.text = "Action: %s | %s frames | %s FPS" % [item["name"],item["frame_count"],item.get("fps",24)]
    if sync_enabled and action_cues.has(active_action):
        var cues: Dictionary=action_cues[active_action]
        pending_action_events=cues.get("events",[]).duplicate(true)
        pending_action_events.sort_custom(func(a:Dictionary,b:Dictionary):return float(a["time_seconds"])<float(b["time_seconds"]))
        for id in cues.get("state_entry_only",[]):emit_action_cue(str(id))
        dispatch_action_events(0.0)

func _process(_delta:float) -> void:
    if active_action.is_empty() or character.sprite_frames==null:return
    if not character.is_playing():return
    var fps:float=character.sprite_frames.get_animation_speed(character.animation)
    dispatch_action_events((character.frame+character.frame_progress)/fps)

func dispatch_action_events(time:float) -> void:
    while pending_action_next<pending_action_events.size() and float(pending_action_events[pending_action_next]["time_seconds"])<=time+0.000001:
        var item:Dictionary=pending_action_events[pending_action_next]
        pending_action_next+=1
        emit_action_cue(str(item["cue"]))

func emit_action_cue(id:String) -> void:
    for i in range(audio_items.size()):
        if str(audio_items[i]["id"])==id:play_audio(i);break
    if id.begins_with("sfx."):
        var effect_id:String=id.trim_prefix("sfx.")
        for i in range(effect_items.size()):
            if str(effect_items[i]["id"])==effect_id:spawn_effect(i,active_action.ends_with("hurt") or active_action.ends_with("die"));break

func spawn_effect(index: int,use_self_target:bool=false) -> void:
    if index < 0 or index >= effect_items.size(): return
    var item: Dictionary = effect_items[index]
    var effect_id:String=str(item["id"])
    if bool(item.get("loop",false)) and effect_loops.has(effect_id) and is_instance_valid(effect_loops[effect_id]):return
    var sprite := AnimatedSprite2D.new()
    sprite.sprite_frames=build_frames(item,asset_root.path_join("vfx"),false)
    sprite.centered=false
    var pivot: Array = item.get("pivot_px",[128,128])
    sprite.offset=-Vector2(float(pivot[0]),float(pivot[1]))
    sprite.z_index=int(item.get("layer_z",0))
    var anchor: String = str(item.get("anchor","owner_chest"))
    sprite.position=Vector2(345,440)
    if anchor=="owner_ground": sprite.position=Vector2(335,625)
    if anchor=="owner_hand": sprite.position=Vector2(460,440)
    # Roar artwork starts its wave at local x=55; pivot is x=128.
    if anchor=="owner_mouth_to_targets":sprite.position=Vector2(435,350)+Vector2(73,0)
    if anchor=="owner_energy":sprite.position=Vector2(80,625)
    var card_anchors:Array[String]=["selected_card","owner_to_selected_card","converted_attack_card","converted_other_card","draw_pile_to_hand","source_pile_to_hand","card_to_discard_pile","exhausted_card","card_cost_anchor","played_card"]
    var target_anchors:Array[String]=["target_contact","target_ground","target_status","resolved_enemy_group"]
    var target_pos:=Vector2(840,625) if anchor=="target_ground" else Vector2(840,470)
    if anchor in target_anchors:
        sprite.position=(Vector2(335,625) if anchor=="target_ground" else Vector2(345,440)) if use_self_target else target_pos
    if anchor in card_anchors:sprite.position=Vector2(840,585)
    if anchor=="card_cost_anchor":sprite.position=Vector2(806,518)
    if anchor=="owner_to_selected_card":
        var arrival:Array=item["target_anchor_px"]
        var card_rect:Array=item["target_card_rect_px"]
        var card_center:=Vector2(float(card_rect[0])+float(card_rect[2])/2.0,float(card_rect[1])+float(card_rect[3])/2.0)
        var point:=Vector2(float(arrival[0]),float(arrival[1]))
        sprite.offset=-point;sprite.position=Vector2(840,585)+point-card_center
    if item.has("segment_anchors_px"):
        var endpoints:Dictionary=item.get("segment_anchors_px",{})
        if not endpoints.has("source") or not endpoints.has("target"):
            record_error("Missing authored endpoints "+effect_id);sprite.free();return
        var source_px:Vector2=Vector2(float(endpoints["source"][0]),float(endpoints["source"][1]))
        var target_px:Vector2=Vector2(float(endpoints["target"][0]),float(endpoints["target"][1]))
        var a:=Vector2(460,440);var b:=target_pos
        if effect_id=="lifesteal":a=Vector2(840,470);b=Vector2(345,440)
        var authored:Vector2=target_px-source_px;var vector:Vector2=b-a
        if authored.length_squared()<0.000001:record_error("Coincident authored endpoints "+effect_id);sprite.free();return
        var u:Vector2=authored.normalized();var v:=Vector2(-u.y,u.x)
        var world_u:Vector2=vector.normalized();var world_v:=Vector2(-world_u.y,world_u.x)
        var stretch:float=vector.length()/authored.length()
        sprite.offset=-source_px
        sprite.transform=Transform2D(world_u*stretch*u.x+world_v*v.x,world_u*stretch*u.y+world_v*v.y,a)
    add_child(sprite); effects.append(sprite)
    if bool(item.get("loop",false)):effect_loops[effect_id]=sprite
    if not bool(item.get("loop",false)):
        sprite.animation_finished.connect(func(): effects.erase(sprite); sprite.queue_free())
    sprite.play(str(item["id"]))
    status.text="Effect: "+str(item["id"])+" | "+anchor

func load_audio_stream(cue: Dictionary) -> AudioStream:
    var path: String = asset_root.path_join("audio").path_join(str(cue.get("file","")))
    var stream: AudioStream
    if path.begins_with("res://"):
        stream=load(path).duplicate() as AudioStream
    elif path.ends_with(".ogg"):
        stream=AudioStreamOggVorbis.load_from_file(path)
    elif path.ends_with(".wav"):
        stream=AudioStreamWAV.load_from_file(path)
    if stream==null: record_error("Cannot load audio "+path); return null
    if stream is AudioStreamOggVorbis: stream.loop=bool(cue.get("loop",false))
    if stream is AudioStreamWAV: stream.loop_mode=AudioStreamWAV.LOOP_FORWARD if bool(cue.get("loop",false)) else AudioStreamWAV.LOOP_DISABLED
    return stream

func play_audio(index: int) -> void:
    if index<0 or index>=audio_items.size(): return
    var cue: Dictionary=audio_items[index]
    var id: String=str(cue.get("id",""))
    if audio_loops.has(id) and is_instance_valid(audio_loops[id]): return
    var now: int=Time.get_ticks_msec()
    if now-int(last_audio_ms.get(id,-100000))<int(cue.get("cooldown_ms",0)): return
    last_audio_ms[id]=now
    var same_cue:Array[AudioStreamPlayer]=[]
    for existing in audio_players:
        if is_instance_valid(existing) and str(existing.get_meta("cue_id",""))==id:same_cue.append(existing)
    while same_cue.size()>=maxi(1,int(cue.get("max_voices",1))):
        var oldest:AudioStreamPlayer=same_cue.pop_front()
        oldest.stop();oldest.queue_free();audio_players.erase(oldest)
    var player:=AudioStreamPlayer.new();player.stream=load_audio_stream(cue)
    if player.stream==null:player.free();return
    player.set_meta("cue_id",id)
    player.volume_db=float(cue.get("gain_db",0));add_child(player);audio_players.append(player)
    if bool(cue.get("loop",false)):audio_loops[id]=player
    player.finished.connect(func():audio_players.erase(player);player.queue_free())
    player.play();status.text="Audio: "+id

func stop_all_owned() -> void:
    pending_action_events.clear();pending_action_next=0;active_action=""
    for sprite in effects:
        if is_instance_valid(sprite):sprite.stop();sprite.queue_free()
    effects.clear();effect_loops.clear()
    for player in audio_players:
        if is_instance_valid(player):player.stop();player.stream=null;player.queue_free()
    audio_players.clear();audio_loops.clear()

func _draw() -> void:
    draw_line(Vector2(35,625),Vector2(1085,625),Color(0.2,0.3,0.36),2)
    draw_circle(Vector2(840,470),55,Color(0.15,0.2,0.25))
    draw_arc(Vector2(840,470),62,0,TAU,64,Color(0.35,0.5,0.58),2)
    draw_rect(Rect2(794,505.5,92,159),Color(0.14,0.18,0.22))
    draw_rect(Rect2(794,505.5,92,159),Color(0.35,0.5,0.58),false,2)
    draw_circle(Vector2(80,625),27,Color(0.1,0.25,0.33))
    draw_arc(Vector2(80,625),28,0,TAU,48,Color(0.4,0.75,0.9),2)

func run_self_test() -> void:
    var animation_count:=0;var frame_count:=0;var effect_count:=0;var effect_frames:=0;var audio_count:=0
    if not bool(animation_manifest.get("render_complete",false)):
        record_error("Animation manifest is not frozen/complete yet")
    if animation_items.size()!=26:record_error("Expected all 26 delivered animation sequences")
    for item in animation_items:
        var frames:=build_frames(item,animation_folder,true)
        var id: String=str(item["name"])
        character.sprite_frames=frames;character.play(id);character.set_frame_and_progress(frames.get_frame_count(id)-1,0)
        if character.frame!=frames.get_frame_count(id)-1:record_error("Cannot seek animation "+id)
        animation_count+=1;frame_count+=frames.get_frame_count(id)
        character.stop();character.sprite_frames=null;texture_cache.clear()
        await get_tree().process_frame
    for item in effect_items:
        var frames:=build_frames(item,asset_root.path_join("vfx"),false)
        var id: String=str(item["id"])
        effect_count+=1;effect_frames+=frames.get_frame_count(id);texture_cache.clear()
    for cue in audio_items:
        var stream:=load_audio_stream(cue)
        if stream!=null and stream.get_length()>0:audio_count+=1
        else:record_error("Empty audio "+str(cue.get("id","")))
    # Asset decode blocks a frame. Let that large delta pass before creating
    # short audio test timers, so they cannot expire on the import frame itself.
    await get_tree().process_frame
    await get_tree().process_frame
    # Actually create one looping and one one-shot player, then destroy ownership.
    for i in range(audio_items.size()):
        if bool(audio_items[i].get("loop",false)):
            var before:int=audio_players.size()
            play_audio(i);play_audio(i)
            if audio_players.size()!=before+1:record_error("Duplicate audio loop created")
            break
    if audio_items.size()>0:play_audio(0)
    if effect_items.size()>0:spawn_effect(0)
    for i in range(effect_items.size()):
        if bool(effect_items[i].get("loop",false)):
            var before:int=effects.size()
            spawn_effect(i);spawn_effect(i)
            if effects.size()!=before+1:record_error("Duplicate VFX loop created")
            break
    # Exercise actual authored endpoint/target metadata, including reverse lifesteal
    # and the external card arrival. These are placement checks, not combat rules.
    for i in range(effect_items.size()):
        var item:Dictionary=effect_items[i]
        var id:String=str(item["id"])
        if item.has("segment_anchors_px"):
            spawn_effect(i)
            var sprite:AnimatedSprite2D=effects.back()
            var pair:Dictionary=item["segment_anchors_px"]
            var local_source:=Vector2(float(pair["source"][0]),float(pair["source"][1]))
            var local_target:=Vector2(float(pair["target"][0]),float(pair["target"][1]))
            var expected_source:=Vector2(840,470) if id=="lifesteal" else Vector2(460,440)
            var expected_target:=Vector2(345,440) if id=="lifesteal" else Vector2(840,470)
            if sprite.to_global(local_source+sprite.offset).distance_to(expected_source)>0.01 or sprite.to_global(local_target+sprite.offset).distance_to(expected_target)>0.01:
                record_error("Endpoint placement mismatch "+id)
        elif id=="feral_transfer":
            spawn_effect(i)
            var sprite:AnimatedSprite2D=effects.back()
            var arrival:Array=item["target_anchor_px"]
            var actual:Vector2=sprite.to_global(Vector2(float(arrival[0]),float(arrival[1]))+sprite.offset)
            if not Rect2(794,505.5,92,159).has_point(actual):record_error("Feral arrival is outside the selected external card")
        elif id=="heavy_impact":
            spawn_effect(i)
            if effects.back().global_position.distance_to(Vector2(840,625))>0.01:record_error("Ground hit is not on target ground")
    var owned_instance_ids:Array[int]=[]
    for player in audio_players:owned_instance_ids.append(player.get_instance_id())
    for sprite in effects:owned_instance_ids.append(sprite.get_instance_id())
    # Give real playback a mixer tick before testing cancellation.
    await get_tree().create_timer(0.08).timeout
    stop_all_owned()
    await get_tree().process_frame
    if not effects.is_empty() or not audio_players.is_empty() or not audio_loops.is_empty():record_error("Lifecycle cleanup failed")
    for instance_id in owned_instance_ids:
        if is_instance_id_valid(instance_id):record_error("Owned node was not actually freed")
    for path in input_hashes:
        if FileAccess.get_sha256(path)!=input_hashes[path]:record_error("Input changed during test: "+path)
    if frame_count!=940:record_error("Expected 940 character frames")
    if effect_count!=40 or effect_frames!=1070:record_error("Expected 40 effects / 1070 effect frames")
    if audio_count!=54:record_error("Expected all 54 logical audio cues to decode")
    var report={"engine_version":Engine.get_version_info().get("string",""),"scope":"standalone Godot asset loading, SpriteFrames, seeks, decode and owned-node cleanup; not STS2 runtime", "animations":animation_count,"animation_frames":frame_count,"effects":effect_count,"effect_frames":effect_frames,"audio_cues_decoded":audio_count,"input_sha256":input_hashes,"failures":failure_messages,"passed":failure_messages.is_empty()}
    var report_path: String=ProjectSettings.globalize_path("res://reports/godot_self_test.json")
    var file:=FileAccess.open(report_path,FileAccess.WRITE)
    if file!=null:file.store_string(JSON.stringify(report,"  "))
    print(JSON.stringify(report))
    action_picker.free();effect_picker.free();audio_picker.free();status.free()
    texture_cache.clear();character.sprite_frames=null
    # Let the dummy/audio mixer retire stopped Ogg playback buffers before shutdown.
    await get_tree().create_timer(0.10).timeout
    get_tree().quit(0 if failure_messages.is_empty() else 1)

func _exit_tree() -> void:
    stop_all_owned()
