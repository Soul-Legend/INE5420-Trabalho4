class_name Fortress
extends Node3D
## Simplified fort inspired by the Fortaleza de Santa Cruz de Anhatomirim:
## a walled courtyard with a gate, round sentry boxes (guaritas) at the
## corners, a barracks, cannons on the wall and torches (several lights).
## Every piece is a hierarchy of nodes (e.g. cannon = carriage + barrel).

const HALF := 12.0  # courtyard half size (m)
const WALL_H := 2.6
const WALL_T := 0.8

var stone := _material(Color(0.72, 0.68, 0.6), 0.9)
var dark_stone := _material(Color(0.45, 0.42, 0.38), 0.95)
var roof := _material(Color(0.62, 0.27, 0.17), 0.8)
var whitewash := _material(Color(0.93, 0.91, 0.86), 0.85)
var iron := _material(Color(0.12, 0.12, 0.13), 0.4, 0.8)
var wood := _material(Color(0.4, 0.26, 0.14), 0.8)


func _ready() -> void:
	_ground()
	_walls()
	for corner in [Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)]:
		_guarita(Vector3(corner.x * HALF, 0, corner.y * HALF))
	_barracks(Vector3(0, 0, -HALF + 3.0))
	for x in [-6.0, -2.0, 2.0, 6.0]:
		_cannon(Vector3(x, WALL_H, HALF), PI)
	for p in [Vector3(-3, 0, HALF - 0.9), Vector3(3, 0, HALF - 0.9), Vector3(-HALF + 0.9, 0, 0), Vector3(HALF - 0.9, 0, 0)]:
		_torch(p)


static func _material(color: Color, roughness: float, metallic := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	m.metallic = metallic
	return m


func _box(size: Vector3, at: Vector3, material: Material, solid := true) -> Node3D:
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = size
	box.material = material
	mesh.mesh = box
	if not solid:
		mesh.position = at
		add_child(mesh)
		return mesh
	var body := StaticBody3D.new()
	body.position = at
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	body.add_child(collision)
	body.add_child(mesh)
	add_child(body)
	return body


func _ground() -> void:
	# Grass outside, paved courtyard inside.
	var noise := NoiseTexture2D.new()
	noise.noise = FastNoiseLite.new()
	noise.seamless = true
	var grass := StandardMaterial3D.new()
	grass.albedo_color = Color(0.36, 0.52, 0.25)
	grass.albedo_texture = noise
	grass.uv1_scale = Vector3(20, 20, 20)
	var ground := _box(Vector3(120, 1, 120), Vector3(0, -0.5, 0), grass)
	ground.name = "Ground"
	var pave := StandardMaterial3D.new()
	pave.albedo_color = Color(0.66, 0.62, 0.55)
	pave.albedo_texture = noise
	pave.uv1_scale = Vector3(8, 8, 8)
	_box(Vector3(2 * HALF, 0.02, 2 * HALF), Vector3(0, 0.01, 0), pave, false)


func _walls() -> void:
	var length := 2 * HALF + WALL_T
	_box(Vector3(length, WALL_H, WALL_T), Vector3(0, WALL_H / 2, -HALF), stone)  # north
	_box(Vector3(WALL_T, WALL_H, length), Vector3(-HALF, WALL_H / 2, 0), stone)  # west
	_box(Vector3(WALL_T, WALL_H, length), Vector3(HALF, WALL_H / 2, 0), stone)  # east
	# South wall with a gate (3 m opening).
	var side := HALF - 1.5
	_box(Vector3(side, WALL_H, WALL_T), Vector3(-1.5 - side / 2, WALL_H / 2, HALF), stone)
	_box(Vector3(side, WALL_H, WALL_T), Vector3(1.5 + side / 2, WALL_H / 2, HALF), stone)
	_box(Vector3(3.8, 0.8, WALL_T * 1.2), Vector3(0, WALL_H + 0.4, HALF), dark_stone)
	# Merlons (ameias) along the north wall.
	for i in range(-11, 12, 2):
		_box(Vector3(0.9, 0.5, WALL_T), Vector3(i, WALL_H + 0.25, -HALF), dark_stone, false)


func _guarita(at: Vector3) -> void:
	var tower := Node3D.new()
	tower.position = at
	add_child(tower)
	var body := MeshInstance3D.new()
	var cylinder := CylinderMesh.new()
	cylinder.top_radius = 0.9
	cylinder.bottom_radius = 1.0
	cylinder.height = 2.0
	cylinder.material = whitewash
	body.mesh = cylinder
	body.position.y = WALL_H + 1.0
	tower.add_child(body)
	var dome := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = 1.0
	sphere.height = 1.2
	sphere.is_hemisphere = true
	sphere.material = roof
	dome.mesh = sphere
	dome.position.y = WALL_H + 2.0
	tower.add_child(dome)
	var base := _box(Vector3(2.4, WALL_H, 2.4), Vector3.ZERO, stone)
	base.reparent(tower)
	base.position = Vector3(0, WALL_H / 2, 0)


func _barracks(at: Vector3) -> void:
	_box(Vector3(10, 3, 4), at + Vector3(0, 1.5, 0), whitewash)
	var top := MeshInstance3D.new()
	var prism := PrismMesh.new()
	prism.size = Vector3(4.6, 1.6, 10.4)
	prism.material = roof
	top.mesh = prism
	top.position = at + Vector3(0, 3.8, 0)
	top.rotation.y = PI / 2
	add_child(top)
	for x in [-3.0, 0.0, 3.0]:
		_box(Vector3(1.0, 2.0, 0.1), at + Vector3(x, 1.0, 2.01), wood, false)


func _cannon(at: Vector3, yaw: float) -> void:
	var cannon := Node3D.new()  # parent: carriage; child: barrel
	cannon.position = at
	cannon.rotation.y = yaw
	add_child(cannon)
	var carriage := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(0.7, 0.35, 1.0)
	box.material = wood
	carriage.mesh = box
	carriage.position.y = 0.18
	cannon.add_child(carriage)
	var barrel := MeshInstance3D.new()
	var tube := CylinderMesh.new()
	tube.top_radius = 0.12
	tube.bottom_radius = 0.18
	tube.height = 1.6
	tube.material = iron
	barrel.mesh = tube
	barrel.position = Vector3(0, 0.5, 0.3)
	barrel.rotation.x = deg_to_rad(80)
	cannon.add_child(barrel)


func _torch(at: Vector3) -> void:
	_box(Vector3(0.12, 1.8, 0.12), at + Vector3(0, 0.9, 0), wood, false)
	var flame := OmniLight3D.new()
	flame.position = at + Vector3(0, 2.0, 0)
	flame.light_color = Color(1.0, 0.62, 0.3)
	flame.light_energy = 2.5
	flame.omni_range = 7.0
	flame.shadow_enabled = false
	add_child(flame)
	var glow := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = 0.12
	sphere.height = 0.24
	var fire := StandardMaterial3D.new()
	fire.emission_enabled = true
	fire.emission = Color(1.0, 0.55, 0.15)
	fire.emission_energy_multiplier = 4.0
	fire.albedo_color = Color(1.0, 0.6, 0.2)
	sphere.material = fire
	glow.mesh = sphere
	glow.position = at + Vector3(0, 1.85, 0)
	add_child(glow)
