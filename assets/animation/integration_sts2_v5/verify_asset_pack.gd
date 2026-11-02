extends SceneTree
## Run in an otherwise empty project. No unpacked VolibearArt directory is permitted.

var failures:Array[String]=[]
var counts:Dictionary={"character_atlases":0,"character_frames":0,"vfx_atlases":0,"vfx_frames":0,"audio_cues":0,"ui_textures":0,"icon_pngs":0,"icon_svgs":0,"painted_icons":0}
var pack_path:String
var report_path:String

func _initialize() -> void:
    var args:=OS.get_cmdline_user_args()
    if args.size()!=2:push_error("Expected PCK path and output report path");quit(2);return
    pack_path=args[0];report_path=args[1]
    run.call_deferred()

func fail(message:String) -> void:
    failures.append(message);push_error(message)

func read_json(path:String) -> Dictionary:
    var f:=FileAccess.open(path,FileAccess.READ)
    if f==null:fail("Missing packed JSON "+path);return {}
    var parser:=JSON.new()
    if parser.parse(f.get_as_text())!=OK or not parser.data is Dictionary:
        fail("Invalid packed JSON "+path);return {}
    return parser.data

func image_size(path:String) -> Vector2i:
    var texture:=ResourceLoader.load(path,"Texture2D",ResourceLoader.CACHE_MODE_IGNORE) as Texture2D
    if texture==null:fail("Cannot load packed texture "+path);return Vector2i.ZERO
    var image:=texture.get_image()
    if image==null or image.is_empty():fail("Cannot decode packed texture "+path);return Vector2i.ZERO
    return image.get_size()

func check_frames(rows:Array,size:Vector2i,label:String) -> void:
    for row in rows:
        var rect:Array=row.get("rect",[])
        if rect.size()!=4:fail("Bad rectangle "+label);continue
        if rect[0]<0 or rect[1]<0 or rect[2]<=0 or rect[3]<=0 or rect[0]+rect[2]>size.x or rect[1]+rect[3]>size.y:
            fail("Packed atlas rectangle out of bounds "+label)

func run() -> void:
    if DirAccess.dir_exists_absolute("res://VolibearArt"):
        fail("Verifier project contains unpacked assets; isolation failed")
    if not ProjectSettings.load_resource_pack(pack_path,false):
        fail("Cannot mount PCK");finish();return
    var root:="res://VolibearArt"
    var animation:=read_json(root+"/animations/manifest.json")
    if not animation.get("render_complete",false):fail("Character manifest not complete")
    for item in animation.get("clips",[])+animation.get("variants",[]):
        var size:=image_size(root+"/animations/"+str(item["atlas"]["image"]))
        var metadata:=read_json(root+"/animations/"+str(item["atlas"]["json"]))
        var frames:Array=metadata.get("frames",[])
        check_frames(frames,size,str(item["name"]))
        counts.character_atlases+=1;counts.character_frames+=frames.size()
    var vfx:=read_json(root+"/vfx/manifest.json")
    for item in vfx.get("effects",[]):
        var size:=image_size(root+"/vfx/"+str(item["atlas"]["image"]))
        check_frames(item.get("frames",[]),size,str(item["id"]))
        counts.vfx_atlases+=1;counts.vfx_frames+=item.get("frames",[]).size()
    var audio:=read_json(root+"/audio/manifest.json")
    for cue in audio.get("cues",[]):
        var path:String=root+"/audio/"+str(cue["file"])
        var stream:=ResourceLoader.load(path,"AudioStream",ResourceLoader.CACHE_MODE_IGNORE) as AudioStream
        if stream==null or stream.get_length()<=0:fail("Cannot decode packed audio "+path)
        else:counts.audio_cues+=1
    var ui:=read_json(root+"/ui/manifest.json")
    for item in ui.get("assets",[]):
        var size:=image_size(root+"/ui/"+str(item["file"]))
        var expected:Array=item["size"]
        if size!=Vector2i(expected[0],expected[1]):fail("UI dimension mismatch "+str(item["id"]))
        counts.ui_textures+=1
    var icons:=read_json(root+"/vfx/icons/manifest.json")
    for item in icons.get("icons",[]):
        for dimension in item.get("files",{}):
            var size:=image_size(root+"/vfx/"+str(item["files"][dimension]["path"]))
            var pixels:=int(dimension)
            if size!=Vector2i(pixels,pixels):fail("Icon dimension mismatch "+str(item["id"]))
            counts.icon_pngs+=1
        if item.has("editable_svg"):
            if image_size(root+"/vfx/"+str(item["editable_svg"]))!=Vector2i.ZERO:counts.icon_svgs+=1
        elif item.has("raster_source"):
            counts.painted_icons+=1
        else:
            fail("Icon missing authoring source "+str(item["id"]))
    read_json(root+"/audio/action_cues.json")
    read_json(root+"/vfx/card_vfx_bindings.json")
    var staged:=read_json(root+"/STAGED_ASSETS.json")
    for item in staged.get("files",[]):
        if str(item["file"]).ends_with(".json"):
            if FileAccess.get_sha256(root+"/"+str(item["file"]))!=str(item["sha256"]):fail("Packed JSON hash mismatch "+str(item["file"]))
    var expected_counts={"character_atlases":26,"character_frames":940,"vfx_atlases":40,"vfx_frames":1070,"audio_cues":54,"ui_textures":18,"icon_pngs":64,"icon_svgs":6,"painted_icons":10}
    for key in expected_counts:
        if counts[key]!=expected_counts[key]:fail("Unexpected count "+str(key))
    finish()

func finish() -> void:
    var result={"scope":"Isolated native Godot PCK mount, JSON integrity, imported texture decode and audio decode; no game registration or STS2 runtime test","engine_version":Engine.get_version_info().get("string",""),"pack_sha256":FileAccess.get_sha256(pack_path),"isolated_project":true,"counts":counts,"failures":failures,"passed":failures.is_empty()}
    var file:=FileAccess.open(report_path,FileAccess.WRITE)
    if file==null:push_error("Cannot save report");quit(2);return
    file.store_string(JSON.stringify(result,"  "));file.close()
    print(JSON.stringify(result))
    quit(0 if failures.is_empty() else 1)

