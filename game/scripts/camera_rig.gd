class_name CameraRig
extends Node3D
## Third-person camera: follows the target from behind and above.
## Mouse (after a click) or Q/E turn the camera; Esc releases the mouse.

@export var target: Player
@export var height := 1.4
@export var distance := 4.5
@export var pitch_deg := -18.0
@export var follow_rate := 8.0

var yaw := 0.0
var _arm := SpringArm3D.new()
var camera := Camera3D.new()


func _ready() -> void:
	top_level = true
	_arm.spring_length = distance
	_arm.margin = 0.2
	_arm.rotation.x = deg_to_rad(pitch_deg)
	add_child(_arm)
	camera.fov = 60.0
	_arm.add_child(camera)
	if target:
		_arm.add_excluded_object(target.get_rid())
		global_position = target.global_position + Vector3.UP * height


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		yaw -= event.relative.x * 0.005
		_arm.rotation.x = clampf(_arm.rotation.x - event.relative.y * 0.004, -1.2, 0.3)


func _process(delta: float) -> void:
	yaw += (Input.get_action_strength("camera_left") - Input.get_action_strength("camera_right")) * 2.0 * delta
	rotation.y = yaw
	if target:
		var goal := target.global_position + Vector3.UP * height
		global_position = global_position.lerp(goal, 1.0 - exp(-follow_rate * delta))
		target.camera_yaw = yaw
