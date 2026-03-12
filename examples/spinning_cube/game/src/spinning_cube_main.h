#pragma once

#include "../include/gdcpp.h"

class SpinningCubeMain : public Node3D {
	GDCLASS(SpinningCubeMain, Node3D)

protected:
	static void _bind_methods();
	void _notification(int p_what);

public:
	void _ready();
	void _process(double p_delta);
};
