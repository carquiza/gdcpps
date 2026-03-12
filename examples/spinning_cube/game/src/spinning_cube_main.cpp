#include "spinning_cube_main.h"

#ifdef SPINNING_CUBE_GDEXTENSION
#include <godot_cpp/classes/directional_light3d.hpp>
#include <godot_cpp/classes/environment.hpp>
#include <godot_cpp/classes/mesh_instance3d.hpp>
#include <godot_cpp/classes/plane_mesh.hpp>
#include <godot_cpp/classes/standard_material3d.hpp>
#include <godot_cpp/classes/world_environment.hpp>
#elif defined(SPINNING_CUBE_MODULE)
#include "scene/3d/light_3d.h"
#include "scene/3d/mesh_instance_3d.h"
#include "scene/3d/world_environment.h"
#include "scene/resources/3d/primitive_meshes.h"
#include "scene/resources/environment.h"
#include "scene/resources/material.h"
#endif

void SpinningCubeMain::_bind_methods() {
}

void SpinningCubeMain::_notification(int p_what) {
	switch (p_what) {
		case NOTIFICATION_READY:
			_ready();
			break;
		case NOTIFICATION_PROCESS:
			_process(get_process_delta_time());
			break;
	}
}

void SpinningCubeMain::_ready() {
	MeshInstance3D *cube = Object::cast_to<MeshInstance3D>(get_node_or_null(NodePath("Cube")));
	if (cube) {
		Ref<StandardMaterial3D> cube_material;
		cube_material.instantiate();
		cube_material->set_albedo(Color(0.18, 0.38, 0.92));
		cube_material->set_metallic(0.18);
		cube_material->set_roughness(0.14);
		cube_material->set_emission(Color(0.20, 0.55, 1.0));
		cube_material->set_emission_energy_multiplier(3.5);
		cube->set_material_override(cube_material);
	}

	if (!get_node_or_null(NodePath("Ground"))) {
		MeshInstance3D *ground = memnew(MeshInstance3D);
		ground->set_name("Ground");
		Ref<PlaneMesh> ground_mesh;
		ground_mesh.instantiate();
		ground_mesh->set_size(Vector2(12.0, 12.0));
		ground->set_mesh(ground_mesh);
		ground->set_position(Vector3(0.0, -0.5, 0.0));

		Ref<StandardMaterial3D> ground_material;
		ground_material.instantiate();
		ground_material->set_albedo(Color(0.07, 0.08, 0.10));
		ground_material->set_roughness(0.94);
		ground->set_material_override(ground_material);
		add_child(ground);
	}

	DirectionalLight3D *light = Object::cast_to<DirectionalLight3D>(get_node_or_null(NodePath("DirectionalLight3D")));
	if (light) {
		light->set_shadow(true);
		light->set_shadow_mode(DirectionalLight3D::SHADOW_PARALLEL_4_SPLITS);
	}

	WorldEnvironment *world_environment = Object::cast_to<WorldEnvironment>(get_node_or_null(NodePath("WorldEnvironment")));
	if (!world_environment) {
		world_environment = memnew(WorldEnvironment);
		world_environment->set_name("WorldEnvironment");
		add_child(world_environment);
	}

	Ref<Environment> environment;
	environment.instantiate();
	environment->set_background(Environment::BG_COLOR);
	environment->set_bg_color(Color(0.03, 0.04, 0.06));
	environment->set_ambient_source(Environment::AMBIENT_SOURCE_COLOR);
	environment->set_ambient_light_color(Color(0.20, 0.22, 0.28));
	environment->set_ambient_light_energy(1.0);
	environment->set_glow_enabled(true);
	environment->set_glow_level(0, 1.0);
	environment->set_glow_level(1, 0.8);
	environment->set_glow_normalized(true);
	environment->set_glow_intensity(0.8);
	environment->set_glow_strength(1.1);
	environment->set_glow_mix(0.2);
	environment->set_glow_bloom(0.15);
	world_environment->set_environment(environment);

	set_process(true);
}

void SpinningCubeMain::_process(double p_delta) {
	Node3D *cube = Object::cast_to<Node3D>(get_node_or_null(NodePath("Cube")));
	if (cube) {
		cube->rotate_y(p_delta);
	}
}
