import bpy
from . import settings
import os
import json


class ALAMO_PT_materialPropertyPanel(bpy.types.Panel):
    bl_label = "Alamo Shader Properties"
    bl_id = "ALAMO_PT_materialPropertyPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    def draw(self, context):
        object = context.object
        layout = self.layout
        col = layout.column()

        # if type(object) != type(None) and object.type == "MESH":
        if type(object) != type(None) and object.type == "MESH":
            material = bpy.context.active_object.active_material
            if material is not None:
                # a None image is needed to represent not using a texture
                if "None" not in bpy.data.images:
                    bpy.data.images.new(name="None", width=1, height=1)
                col.prop(material.shaderList, "shaderList")
                if material.shaderList.shaderList != "alDefault.fx":
                    shader_props = settings.material_parameter_dict[
                        material.shaderList.shaderList
                    ]
                    for shader_prop in shader_props:
                        # because contains() doesn't exist, apparently
                        if shader_prop.find("Texture") > -1:
                            layout.prop_search(
                                material, shader_prop, bpy.data, "images"
                            )
                            # layout.template_ID(material, shader_prop, new="image.new", open="image.open")


class ALAMO_PT_materialPropertySubPanel(bpy.types.Panel):
    bl_label = "Additional Properties"
    bl_parent_id = "ALAMO_PT_materialPropertyPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        obj = context.object
        layout = self.layout
        col = layout.column()

        if obj is not None and obj.type == "MESH":
            material = bpy.context.active_object.active_material
            if (
                material is not None
                and material.shaderList.shaderList != "alDefault.fx"
            ):
                shader_props = settings.material_parameter_dict[
                    material.shaderList.shaderList
                ]
                for shader_prop in shader_props:
                    # because contains() doesn't exist, apparently
                    if shader_prop.find("Texture") == -1:
                        col.prop(material, shader_prop)

def get_shader_enum(self, context):
    return [
        (name, name, "", "", i)
        for i, name in enumerate(settings.material_parameter_dict.keys())
    ]

def get_default_shader_index():
    keys = list(settings.material_parameter_dict.keys())
    return keys.index("alDefault.fx")

class shaderListProperties(bpy.types.PropertyGroup):
    shaderList: bpy.props.EnumProperty(
        items=get_shader_enum, # This lets the dicionaries populate before building UI stuff
        description="Choose ingame Shader",
        default=get_default_shader_index(),
    )

# Registration ####################################################################################
classes = (
    shaderListProperties,
    ALAMO_PT_materialPropertyPanel,
    ALAMO_PT_materialPropertySubPanel,
)

def load_json():
    addon_dir = os.path.dirname(__file__)
    shaders_dir = os.path.join(addon_dir, 'materials')

    data = {}
    for filename in os.listdir(shaders_dir):
        if filename.lower().endswith(".json"):
            path = os.path.join(shaders_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    parse_json(data)

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")

def parse_json(data):
    for name in data:

        match data[name].get("propertyType"):
            case "StringProperty":
                setattr(
                    bpy.types.Material,
                    name,
                    bpy.props.StringProperty(default="None"))
            case "FloatProperty":
                setattr(
                    bpy.types.Material,
                    name,
                    bpy.props.FloatProperty(
                        min = data[name].get("min"),
                        max = data[name].get("max"),
                        default = data[name].get("default")))
            case "FloatVectorProperty":
                setattr(
                    bpy.types.Material,
                    name,
                    bpy.props.FloatVectorProperty(
                        min = data[name].get("min"),
                        max = data[name].get("max"),
                        size = data[name].get("size"),
                        default = tuple(data[name].get("default"))))
            case _:
                return
        settings.material_parameter_list.append(name)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Material.shaderList = bpy.props.PointerProperty(type=shaderListProperties)
    load_json()

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    for name in settings.material_parameter_list:
        if hasattr(bpy.types.Material, name):
            delattr(bpy.types.Material, name)

if __name__ == "__main__":
    register()
