class_name Coin
extends Area3D
## Collectable coin: spins, bobs and emits `collected` when the player touches it.

signal collected(coin: Coin)

var _time := randf() * TAU
var _mesh := MeshInstance3D.new()
var _base_y := 0.0


func _ready() -> void:
	var shape := SphereShape3D.new()
	shape.radius = 0.45
	var collision := CollisionShape3D.new()
	collision.shape = shape
	add_child(collision)

	var disc := CylinderMesh.new()
	disc.top_radius = 0.28
	disc.bottom_radius = 0.28
	disc.height = 0.06
	var gold := StandardMaterial3D.new()
	gold.albedo_color = Color(1.0, 0.78, 0.25)
	gold.metallic = 1.0
	gold.roughness = 0.25
	gold.emission_enabled = true
	gold.emission = Color(0.6, 0.4, 0.05)
	disc.material = gold
	_mesh.mesh = disc
	_mesh.rotation.x = PI / 2
	add_child(_mesh)
	_base_y = position.y
	body_entered.connect(_on_body_entered)


func _process(delta: float) -> void:
	_time += delta
	rotation.y = _time * 2.0
	position.y = _base_y + 0.1 * sin(_time * 3.0)


func place(at: Vector3) -> void:
	position = at
	_base_y = at.y


func _on_body_entered(body: Node3D) -> void:
	if body is Player:
		collected.emit(self)
