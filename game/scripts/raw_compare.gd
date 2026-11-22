class_name RawCompare
extends Node3D
## Curiosity scene: what if the capture were used directly, with no treatment?
##
## Two copies of the character walk side by side at the same speed, as a game
## controller would move them, with the SAME walking segment of one take
## (Movimentos02, 24.0-26.6 s):
##   - "sem tratamento": the window exactly as recorded (walk_raw): the hips
##     travel recorded in the capture is added to the controller's motion,
##     the body faces wherever the student was facing, and every 2.6 s the clip
##     restarts and the character jumps back to the start pose and position;
##   - "tratado": the game clip (loop point chosen, travel removed, heading
##     aligned, start/end difference spread over the clip).
## The only thing done to the raw copy is placing its first frame on its lane.

signal finished

const CHARACTER_PATH := "res://assets/personagem.glb"
const CLIPS_PATH := "res://assets/clips.json"
const DURATION := 18.0

var speed := 1.0
var camera := Camera3D.new()
var _roots: Array[Node3D] = []
var _time := 0.0


func _ready() -> void:
	var clips: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CLIPS_PATH))
	speed = clips["walk"]["speed_m_s"]
	_add_actor("walk_raw", Vector3(-9, 0, -1.3), "SEM tratamento\n(captura usada direto)", Color(1.0, 0.45, 0.4))
	_add_actor("walk", Vector3(-9, 0, 1.3), "COM tratamento\n(clipe do jogo)", Color(0.5, 1.0, 0.55))
	camera.fov = 55.0
	add_child(camera)
	camera.make_current()

	var hud := CanvasLayer.new()
	add_child(hud)
	var caption := Label.new()
	caption.text = ("Mesma caminhada da captura (Movimentos02, 24,0-26,6 s), mesma velocidade\n"
		+ "Sem tratamento: o deslocamento gravado soma-se ao do jogo, a direção do corpo não segue o\n"
		+ "movimento e, a cada repetição (2,6 s), o personagem salta de volta para a pose e a posição iniciais.")
	caption.position = Vector2(20, 14)
	caption.add_theme_font_size_override("font_size", 20)
	caption.add_theme_color_override("font_outline_color", Color.BLACK)
	caption.add_theme_constant_override("outline_size", 6)
	hud.add_child(caption)


func _add_actor(animation: String, start: Vector3, text: String, color: Color) -> void:
	var root := Node3D.new()
	root.position = start
	root.rotation.y = -PI / 2  # walk towards +X
	add_child(root)
	var model: Node3D = (load(CHARACTER_PATH) as PackedScene).instantiate()
	model.rotation.y = PI  # glTF looks to +Z; a Node3D moves along -Z
	root.add_child(model)
	var player: AnimationPlayer = model.find_children("*", "AnimationPlayer", true, false)[0]
	player.get_animation(animation).loop_mode = Animation.LOOP_LINEAR
	player.play(animation)
	player.seek(0.0, true)
	# Place the first frame on the lane (the raw clip starts somewhere in the capture room).
	var skeleton: Skeleton3D = model.find_children("*", "Skeleton3D", true, false)[0]
	var hips_world := skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("Hips")).origin
	var hips_local := root.global_transform.affine_inverse() * hips_world
	model.position -= Vector3(hips_local.x, 0, hips_local.z)

	var label := Label3D.new()
	label.text = text
	label.position = Vector3(0, 2.35, 0)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 56
	label.outline_size = 10
	label.modulate = color
	root.add_child(label)
	_roots.append(root)


func _process(delta: float) -> void:
	_time += delta
	for root in _roots:
		root.position.x += speed * delta  # what a game controller does every frame
	# Camera ahead of the pair, looking back at them: both lanes side by side.
	var mid := _roots[1].position.x
	camera.global_position = Vector3(mid + 6.0, 2.0, 0.0)
	camera.look_at(Vector3(mid, 1.0, 0.0), Vector3.UP)
	if _time >= DURATION:
		finished.emit()
