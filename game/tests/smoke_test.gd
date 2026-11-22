extends SceneTree
## Headless checks of the game logic.
## Run: godot --headless --path game -s res://tests/smoke_test.gd

var _failures := 0


func _initialize() -> void:
	_run.call_deferred()


func _check(condition: bool, message: String) -> void:
	print(("  ok   " if condition else "  FAIL ") + message)
	if not condition:
		_failures += 1


func _frames(count: int) -> void:
	for i in count:
		await physics_frame


func _walk_speed_after(player: Player, set_name: String, run: bool, frames: int) -> float:
	player.global_position = Vector3(0, 0.05, 8)
	player.velocity = Vector3.ZERO
	player.set_animation_set(set_name)
	player.autopilot = [[frames / 60.0 + 0.5, Vector2(0, 1), run]]
	await _frames(frames)
	return player.velocity.length()


func _run() -> void:
	var main: Node3D = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	await _frames(2)
	var player: Player = main.player
	var clips: Dictionary = player.clips

	print("Animation clips (both sets)")
	for set_name in Player.SETS:
		for clip in ["idle", "walk", "run"]:
			var name: String = Player.SETS[set_name][clip]
			var anim := player.anim_player.get_animation(name)
			_check(anim != null and anim.loop_mode == Animation.LOOP_LINEAR, "%s exists and loops" % name)
			# Catches frame-rate mistakes in the export (e.g. clips playing 4x too fast).
			var expected: float = clips[name]["length_s"]
			_check(absf(anim.length - expected) < 0.05,
				"%s lasts %.2f s as baked (%.2f s)" % [name, anim.length, expected])
	_check(player.anim_tree.active, "AnimationTree is active")

	print("Complete capture takes (MoCap show)")
	for take in clips["mocap_takes"]:
		var anim := player.anim_player.get_animation(take["action"])
		_check(anim != null and absf(anim.length - take["seconds"]) < 0.1,
			"%s: %.1f s" % [take["action"], take["seconds"]])

	print("Hierarchical skeleton")
	var skeleton: Skeleton3D = player.model.find_children("*", "Skeleton3D", true, false)[0]
	_check(skeleton.get_bone_count() == 28, "28 bones (got %d)" % skeleton.get_bone_count())
	var hips := skeleton.find_bone("Hips")
	_check(hips >= 0 and skeleton.get_bone_parent(hips) == -1, "Hips is the root bone")
	_check(skeleton.get_bone_parent(skeleton.find_bone("LeftForeArm")) == skeleton.find_bone("LeftArm"),
		"LeftForeArm is a child of LeftArm")

	print("Blend weights")
	for set_name in Player.SETS:
		var s: Dictionary = player.speeds[set_name]
		var half: Dictionary = player.blend_weights((s["walk"] + s["run"]) / 2, set_name)
		_check(is_equal_approx(player.blend_weights(0.0, set_name)["idle"], 1.0)
			and is_equal_approx(player.blend_weights(s["walk"], set_name)["walk"], 1.0)
			and is_equal_approx(half["walk"], 0.5) and is_equal_approx(half["run"], 0.5),
			"%s: 0 -> idle, walk speed -> walk, half way -> 50/50" % set_name)

	print("Movement")
	for coin in main.coins:
		coin.place(Vector3(20, -5, 20))  # out of the way
	for set_name in Player.SETS:
		var k := player.scale_of(set_name)
		var walk := await _walk_speed_after(player, set_name, false, 150)
		_check(absf(walk - player.speeds[set_name]["walk"] * k) < 0.05,
			"%s: walking reaches %.2f m/s" % [set_name, walk])
		var run := await _walk_speed_after(player, set_name, true, 150)
		_check(absf(run - player.speeds[set_name]["run"] * k) < 0.05,
			"%s: running reaches %.2f m/s" % [set_name, run])
	player.autopilot = [[1.5, Vector2.ZERO, false]]
	await _frames(90)
	_check(player.velocity.length() < 0.01, "stops when there is no input")
	player.set_animation_set("pro")
	player.toggle_animation_set()
	_check(player.animation_set == "mocap", "Tab switches to the capture animations")
	player.toggle_animation_set()
	_check(player.animation_set == "pro", "Tab switches back to the procedural animations")

	print("Coins")
	var coin: Coin = main.coins[0]
	coin.place(player.global_position + Vector3(0, 0.8, 0))
	await _frames(5)
	_check(main.score == 1, "touching a coin scores (score = %d)" % main.score)
	_check(coin.position.distance_to(player.global_position) > 1.0, "the coin respawns elsewhere")

	print("%d failure(s)" % _failures)
	quit(1 if _failures else 0)
