#pragma once

#ifdef SPINNING_CUBE_GDEXTENSION

#include <godot_cpp/classes/node3d.hpp>
#include <godot_cpp/core/class_db.hpp>

using namespace godot;

#elif defined(SPINNING_CUBE_MODULE)

#include "core/object/class_db.h"
#include "scene/3d/node_3d.h"

#else
#error "Define SPINNING_CUBE_GDEXTENSION or SPINNING_CUBE_MODULE before including gdcpp.h"
#endif
