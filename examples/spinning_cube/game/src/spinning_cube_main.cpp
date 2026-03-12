#include "spinning_cube_main.h"

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
	set_process(true);
}

void SpinningCubeMain::_process(double p_delta) {
	Node3D *cube = Object::cast_to<Node3D>(get_node_or_null(NodePath("Cube")));
	if (cube) {
		cube->rotate_y(p_delta);
	}
}
