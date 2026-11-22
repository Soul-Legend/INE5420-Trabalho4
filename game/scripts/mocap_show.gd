class_name MocapShow
extends Node3D
## Scripted scene: the character performs the COMPLETE class capture takes,
## one after the other, with no player input. The actions keep the hips
## trajectory recorded in the capture room (root motion), so the character
## walks around the courtyard exactly as the student did.
## A camera orbits slowly around the character and a caption names the take.

signal finished

const CHARACTER_PATH := "res://assets/personagem.glb"
const CLIPS_PATH := "res://assets/clips.json"

var takes: Array = []
var model: Node3D
var anim_player: AnimationPlayer
var skeleton: Skeleton3D
var camera := Camera3D.new()
var caption := Label.new()

var _index := -1
var _hips := -1
var _orbit := 0.0
var _focus := Vector3.ZERO


func _ready() -> void:
	var clips: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CLIPS_PATH))
	takes = clips["mocap_takes"]
	model = (load(CHARACTER_PATH) as PackedScene).instantiate()
	add_child(model)
	anim_player = model.find_children("*", "AnimationPlayer", true, false)[0]
	skeleton = model.find_children("*", "Skeleton3D", true, false)[0]
	_hips = skeleton.find_bone("Hips")
	anim_player.animation_finished.connect(func(_name): _next())

	camera.fov = 55.0
	add_child(camera)
	camera.make_current()
	var hud := CanvasLayer.new()
	add_child(hud)
	caption.position = Vector2(20, 16)
	caption.add_theme_font_size_override("font_size", 24)
	caption.add_theme_color_override("font_outline_color", Color.BLACK)
	caption.add_theme_constant_override("outline_size", 6)
	hud.add_child(caption)
	_next()


func _next() -> void:
	_index += 1
	if _index >= takes.size():
		finished.emit()
		return
	var take: Dictionary = takes[_index]
	var anim := anim_player.get_animation(take["action"])
	anim.loop_mode = Animation.LOOP_NONE
	anim_player.play(take["action"])
	_focus = _hips_position()


func _hips_position() -> Vector3:
	return skeleton.global_transform * skeleton.get_bone_global_pose(_hips).origin


func _process(delta: float) -> void:
	if _index < 0 or _index >= takes.size():
		return
	var take: Dictionary = takes[_index]
	caption.text = "Captura de movimentos da turma (sem controle do jogador)\n%s  -  tomada %d de %d  -  %.0f / %.0f s" % [
		take["action"].trim_prefix("mocap_"), _index + 1, takes.size(),
		anim_player.current_animation_position, take["seconds"]]
	var hips := _hips_position()
	_focus = _focus.lerp(Vector3(hips.x, 0.9, hips.z), 1.0 - exp(-3.0 * delta))
	_orbit += delta * 0.12
	camera.global_position = _focus + Vector3(sin(_orbit) * 4.5, 1.2, cos(_orbit) * 4.5)
	camera.look_at(_focus, Vector3.UP)
