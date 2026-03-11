#include "register_types.h"

#ifdef SPINNING_CUBE_GDEXTENSION
#include <gdextension_interface.h>
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/core/defs.hpp>
#include <godot_cpp/godot.hpp>
using namespace godot;
#elif defined(SPINNING_CUBE_MODULE)
#include "core/object/class_db.h"
#endif

#include "src/spinning_cube_main.h"

void initialize_spinning_cube_module(ModuleInitializationLevel p_level) {
	if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
		return;
	}
	GDREGISTER_CLASS(SpinningCubeMain);
}

void uninitialize_spinning_cube_module(ModuleInitializationLevel p_level) {
	if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
		return;
	}
}

#ifdef SPINNING_CUBE_GDEXTENSION
extern "C" {
GDExtensionBool GDE_EXPORT spinning_cube_library_init(
		GDExtensionInterfaceGetProcAddress p_get_proc_address,
		GDExtensionClassLibraryPtr p_library,
		GDExtensionInitialization *r_initialization) {
	GDExtensionBinding::InitObject init_obj(p_get_proc_address, p_library, r_initialization);
	init_obj.register_initializer(initialize_spinning_cube_module);
	init_obj.register_terminator(uninitialize_spinning_cube_module);
	init_obj.set_minimum_library_initialization_level(MODULE_INITIALIZATION_LEVEL_SCENE);
	return init_obj.init();
}
}
#endif
