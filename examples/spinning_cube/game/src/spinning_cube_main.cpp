#include "spinning_cube_main.h"

void SpinningCubeMain::_bind_methods() {
}

#ifdef SPINNING_CUBE_MODULE
void SpinningCubeMain::_notification(int p_what) {
	Node3D::_notification(p_what);

	switch (p_what) {
		case NOTIFICATION_READY:
			_ready();
			break;
		case NOTIFICATION_PROCESS:
			_process(get_process_delta_time());
			break;
	}
}
#endif

void SpinningCubeMain::_ready() {
	set_process(true);
}

void SpinningCubeMain::_process(double p_delta) {
	rotate_y(p_delta);
}
