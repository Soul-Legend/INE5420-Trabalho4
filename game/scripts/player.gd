class_name Player
extends CharacterBody3D
## Character controlled by the player.
##
## The model is a hierarchical model: a skeleton of 28 bones taken from the
## class motion capture. Each bone's pose is relative to its parent, so moving
## the hips carries the whole body, moving the upper arm carries forearm and
## hand, and so on (forward kinematics, done by Skeleton3D).
##
## Two animation sets drive the same skeleton:
##   "pro"   - procedural idle/walk/run cycles (two-bone leg IK, arm swing,
##             pelvis and spine rotation; blender/procedural_gait.py);
##   "mocap" - idle/walk/run clips cut from the class captures
##             (blender/build_character.py).
## Each set is a BlendSpace1D (idle at 0, walk and run at their measured
## speeds); a Blend2 node cross-fades between the sets (Tab key).
## The clips play "in place" and the controller moves the body at the speed
## the clip was made for, so the feet do not slide.

signal speed_changed(speed: float, weights: Dictionary, set_name: String)

## AI-generated character bound to the capture rig; the rigid mannequin is the fallback.
const CHARACTER_PATH := "res://assets/personagem.glb"
const MANNEQUIN_PATH := "res://assets/manequim.glb"
const CLIPS_PATH := "res://assets/clips.json"
const SETS := {
	"pro": {"idle": "idle_pro", "walk": "walk_pro", "run": "run_pro", "scale": 1.0,
			"label": "procedural (IK)"},
	"mocap": {"idle": "idle", "walk": "walk", "run": "run", "scale": 1.4,
			"label": "captura da turma (MoCap)"},
}

@export var acceleration := 6.0  # m/s^2
@export var turn_rate := 10.0  # larger = turns faster

var animation_set := "pro"
var speeds := {}  # set -> {"walk": m/s, "run": m/s} at the clip's own rate
var camera_yaw := 0.0  # set by the camera rig: movement is camera-relative
var model: Node3D
var anim_player: AnimationPlayer
var anim_tree: AnimationTree
var clips: Dictionary
## Scripted input for demos/tests: [[seconds, Vector2 direction, run?], ...].
var autopilot: Array = []:
	set(value):
		autopilot = value
		_autopilot_clock = 0.0  # a new script starts from its first step

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")
var _autopilot_clock := 0.0
var _set_blend := 0.0  # 0 = pro, 1 = mocap (smoothed)


func _ready() -> void:
	clips = JSON.parse_string(FileAccess.get_file_as_string(CLIPS_PATH))
	for set_name in SETS:
		speeds[set_name] = {
			"walk": clips[SETS[set_name]["walk"]]["speed_m_s"],
			"run": clips[SETS[set_name]["run"]]["speed_m_s"],
		}
	_build_collision()
	_build_model()
	_build_animation_tree()


func _build_collision() -> void:
	var shape := CapsuleShape3D.new()
	shape.radius = 0.3
	shape.height = 1.7
	var collision := CollisionShape3D.new()
	collision.shape = shape
	collision.position.y = 0.85
	add_child(collision)


func _build_model() -> void:
	var path := CHARACTER_PATH if ResourceLoader.exists(CHARACTER_PATH) else MANNEQUIN_PATH
	model = (load(path) as PackedScene).instantiate()
	# glTF characters look to +Z; a Node3D moves "forward" along -Z.
	model.rotation.y = PI
	add_child(model)
	anim_player = model.find_children("*", "AnimationPlayer", true, false)[0]
	for set_name in SETS:
		for clip in ["idle", "walk", "run"]:
			anim_player.get_animation(SETS[set_name][clip]).loop_mode = Animation.LOOP_LINEAR


func _locomotion(set_name: String) -> AnimationNodeBlendSpace1D:
	var space := AnimationNodeBlendSpace1D.new()
	space.min_space = 0.0
	space.max_space = speeds[set_name]["run"]
	for point in [["idle", 0.0], ["walk", speeds[set_name]["walk"]], ["run", speeds[set_name]["run"]]]:
		var node := AnimationNodeAnimation.new()
		node.animation = SETS[set_name][point[0]]
		space.add_blend_point(node, point[1], -1, point[0])
	return space


func _build_animation_tree() -> void:
	# loco_pro --------------------------------> mix(0)
	# loco_mocap -> ts_mocap (x1.4 faster) ----> mix(1) -> output
	var graph := AnimationNodeBlendTree.new()
	graph.add_node("loco_pro", _locomotion("pro"), Vector2(0, 0))
	graph.add_node("loco_mocap", _locomotion("mocap"), Vector2(0, 200))
	graph.add_node("ts_mocap", AnimationNodeTimeScale.new(), Vector2(200, 200))
	graph.add_node("mix", AnimationNodeBlend2.new(), Vector2(400, 100))
	graph.connect_node("ts_mocap", 0, "loco_mocap")
	graph.connect_node("mix", 0, "loco_pro")
	graph.connect_node("mix", 1, "ts_mocap")
	graph.connect_node("output", 0, "mix")

	anim_tree = AnimationTree.new()
	anim_tree.name = "AnimationTree"
	add_child(anim_tree)
	anim_tree.anim_player = anim_tree.get_path_to(anim_player)
	anim_tree.tree_root = graph
	anim_tree.set("parameters/ts_mocap/scale", SETS["mocap"]["scale"])
	anim_tree.active = true


func set_animation_set(set_name: String) -> void:
	animation_set = set_name


func toggle_animation_set() -> void:
	set_animation_set("mocap" if animation_set == "pro" else "pro")


func scale_of(set_name: String) -> float:
	return SETS[set_name]["scale"]


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_set"):
		toggle_animation_set()


func _physics_process(delta: float) -> void:
	var command := _read_command(delta)
	var direction := Vector3(command.x, 0.0, -command.y).rotated(Vector3.UP, camera_yaw)
	if direction.length() > 1.0:
		direction = direction.normalized()

	var scale := scale_of(animation_set)
	var target_speed: float = speeds[animation_set]["run" if command.z > 0.5 else "walk"] * scale
	var horizontal := Vector3(velocity.x, 0.0, velocity.z)
	horizontal = horizontal.move_toward(direction * target_speed, acceleration * delta)
	velocity.x = horizontal.x
	velocity.z = horizontal.z
	velocity.y = 0.0 if is_on_floor() else velocity.y - _gravity * delta
	move_and_slide()

	if direction.length() > 0.1:
		# Face the walking direction: rotation.y = 0 looks to -Z.
		var target_yaw := atan2(-direction.x, -direction.z)
		rotation.y = lerp_angle(rotation.y, target_yaw, 1.0 - exp(-turn_rate * delta))

	# Each blend space receives the speed in its own clip units.
	var speed := Vector3(velocity.x, 0.0, velocity.z).length()
	anim_tree.set("parameters/loco_pro/blend_position", speed / scale_of("pro"))
	anim_tree.set("parameters/loco_mocap/blend_position", speed / scale_of("mocap"))
	_set_blend = move_toward(_set_blend, 1.0 if animation_set == "mocap" else 0.0, delta * 3.0)
	anim_tree.set("parameters/mix/blend_amount", _set_blend)
	speed_changed.emit(speed, blend_weights(speed / scale), animation_set)


## Returns Vector3(x, forward, run) from the keyboard or from the autopilot.
func _read_command(delta: float) -> Vector3:
	if not autopilot.is_empty():
		_autopilot_clock += delta
		var step: Array = autopilot[0]
		if _autopilot_clock >= step[0]:
			_autopilot_clock -= step[0]
			autopilot.pop_front()
		if step.size() > 3 and step[3] != "" and step[3] != animation_set:
			set_animation_set(step[3])
		var dir: Vector2 = step[1]
		return Vector3(dir.x, dir.y, 1.0 if step[2] else 0.0)
	var input := Input.get_vector("move_left", "move_right", "move_back", "move_forward")
	return Vector3(input.x, input.y, 1.0 if Input.is_action_pressed("run") else 0.0)


## Weight of each clip for a speed (in clip units) of the current set,
## the same linear rule used by BlendSpace1D.
func blend_weights(speed: float, set_name := "") -> Dictionary:
	var s: Dictionary = speeds[set_name if set_name != "" else animation_set]
	if speed <= s["walk"]:
		var t := clampf(speed / s["walk"], 0.0, 1.0)
		return {"idle": 1.0 - t, "walk": t, "run": 0.0}
	var u := clampf((speed - s["walk"]) / (s["run"] - s["walk"]), 0.0, 1.0)
	return {"idle": 0.0, "walk": 1.0 - u, "run": u}
