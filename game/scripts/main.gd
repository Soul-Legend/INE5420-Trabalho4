extends Node3D
## Builds the game scene: sky and sun, the fort, the player, the camera,
## the coins and the HUD.
##
## Command-line options (after "--"):
##   --demo                 scripted WASD tour with the procedural animations (video)
##   --mocap-show           scripted scene: the complete class capture takes, no input
##   --screenshots=DIR      saves PNG frames at key moments

const COIN_COUNT := 8

var player: Player
var camera_rig: CameraRig
var score := 0
var coins: Array[Coin] = []

var _score_label := Label.new()
var _state_label := Label.new()
var _rng := RandomNumberGenerator.new()
var _shots_dir := ""
var _shot_times := [2.0, 5.5, 9.0, 12.5, 15.0]
var _clock := 0.0


func _ready() -> void:
	InputSetup.register()
	_rng.seed = 2026
	_build_environment()
	add_child(Fortress.new())
	if "--mocap-show" in OS.get_cmdline_user_args():
		var show := MocapShow.new()
		show.position = Vector3(0, 0, 2)
		add_child(show)
		show.finished.connect(get_tree().quit)
		_read_options()
		return
	_build_player()
	_build_coins()
	_build_hud()
	_read_options()


func _build_environment() -> void:
	var sky_material := ProceduralSkyMaterial.new()
	sky_material.sky_top_color = Color(0.32, 0.55, 0.85)
	sky_material.sky_horizon_color = Color(0.75, 0.82, 0.9)
	var sky := Sky.new()
	sky.sky_material = sky_material
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ssao_enabled = true
	env.glow_enabled = true
	var world := WorldEnvironment.new()
	world.environment = env
	add_child(world)

	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(deg_to_rad(-48), deg_to_rad(-35), 0)
	sun.light_energy = 1.2
	sun.shadow_enabled = true
	add_child(sun)


func _build_player() -> void:
	player = Player.new()
	player.name = "Player"
	player.position = Vector3(0, 0.05, 8)
	add_child(player)
	camera_rig = CameraRig.new()
	camera_rig.target = player
	add_child(camera_rig)
	camera_rig.camera.make_current()


func _build_coins() -> void:
	for i in COIN_COUNT:
		var coin := Coin.new()
		add_child(coin)
		coin.place(_random_spot())
		coin.collected.connect(_on_coin_collected)
		coins.append(coin)


func _random_spot() -> Vector3:
	# Inside the courtyard, away from walls and from the barracks (north).
	var limit := Fortress.HALF - 2.0
	return Vector3(_rng.randf_range(-limit, limit), 0.8, _rng.randf_range(-Fortress.HALF + 6.5, limit))


func _on_coin_collected(coin: Coin) -> void:
	score += 1
	_score_label.text = "Moedas: %d" % score
	coin.place(_random_spot())


func _build_hud() -> void:
	var hud := CanvasLayer.new()
	add_child(hud)
	_score_label.text = "Moedas: 0"
	_score_label.position = Vector2(20, 16)
	_score_label.add_theme_font_size_override("font_size", 30)
	_score_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_score_label.add_theme_constant_override("outline_size", 6)
	hud.add_child(_score_label)

	_state_label.position = Vector2(20, 60)
	_state_label.add_theme_font_size_override("font_size", 18)
	_state_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_state_label.add_theme_constant_override("outline_size", 4)
	hud.add_child(_state_label)
	player.speed_changed.connect(_on_speed_changed)

	var help := Label.new()
	help.text = "WASD: andar   Shift: correr   Tab: trocar animação (procedural / captura)   Q/E ou mouse: câmera"
	help.add_theme_font_size_override("font_size", 16)
	help.add_theme_color_override("font_outline_color", Color.BLACK)
	help.add_theme_constant_override("outline_size", 4)
	help.anchor_top = 1.0
	help.anchor_bottom = 1.0
	help.position = Vector2(20, -40)
	hud.add_child(help)


func _on_speed_changed(speed: float, weights: Dictionary, set_name: String) -> void:
	_state_label.text = "Animação: %s   |   %.2f m/s   |   parado %3d%%   andar %3d%%   correr %3d%%" % [
		Player.SETS[set_name]["label"], speed,
		roundi(weights["idle"] * 100), roundi(weights["walk"] * 100), roundi(weights["run"] * 100)
	]


func _read_options() -> void:
	var args := OS.get_cmdline_user_args()
	if "--demo" in args:
		_demo()
	for arg in args:
		if arg.begins_with("--screenshots="):
			_shots_dir = arg.get_slice("=", 1)
			DirAccess.make_dir_recursive_absolute(_shots_dir)


func _demo() -> void:
	# Scripted WASD session (procedural animations): coins on the path, then
	# idle, walk, turn, run, curve, walk back and stop. Equivalent keys in comments.
	# The camera stays at yaw 0, so W = -Z (towards the barracks) and D = +X.
	var path := [Vector3(0, 0.8, 5.5), Vector3(-1.2, 0.8, 2.6), Vector3(-1.6, 0.8, -1.5),
				Vector3(2.0, 0.8, -4.6), Vector3(6.6, 0.8, -1.0), Vector3(5.0, 0.8, 2.6)]
	for i in path.size():
		coins[i].place(path[i])
	camera_rig.yaw = 0.0
	player.set_animation_set("pro")
	player.autopilot = [
		[2.0, Vector2.ZERO, false],             # parado (respiração)
		[3.0, Vector2(0, 1), false],            # W: andar
		[2.0, Vector2(-0.6, 0.8), false],       # W+A: curva andando
		[2.5, Vector2(0, 1), true],             # W+Shift: correr
		[3.0, Vector2(1, 0), true],             # D+Shift: correr para a direita
		[2.5, Vector2(0, -1), true],            # S+Shift: correr de volta
		[3.0, Vector2(-1, 0), false],           # A: andar para a esquerda
		[1.5, Vector2.ZERO, false],             # parar
		[2.0, Vector2(-0.5, 0.85), false],      # W+A: andar
		[2.0, Vector2.ZERO, false],
	]
	_shot_times = [1.0, 4.0, 9.0, 12.5, 16.0, 20.0]


func _process(delta: float) -> void:
	if _shots_dir.is_empty() or _shot_times.is_empty():
		return
	_clock += delta
	if _clock >= _shot_times[0]:
		var image := get_viewport().get_texture().get_image()
		image.save_png("%s/demo_%04.1fs.png" % [_shots_dir, _shot_times[0]])
		_shot_times.pop_front()
