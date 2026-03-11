#pragma once

#ifdef SPINNING_CUBE_MODULE
#include "modules/register_module_types.h"
#elif defined(SPINNING_CUBE_GDEXTENSION)
#include <godot_cpp/godot.hpp>
using namespace godot;
#endif

void initialize_spinning_cube_module(ModuleInitializationLevel p_level);
void uninitialize_spinning_cube_module(ModuleInitializationLevel p_level);
