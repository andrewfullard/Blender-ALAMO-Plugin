from . import_alo import ALO_Importer
from . export_ala import ALA_Exporter
from . export_alo import ALO_Exporter
from . import_ala import ALA_Importer
from . import validation
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.props import *
import mathutils
import bpy
bl_info = {
    "name": "ALAMO Tools",
    "author": "Gaukler, evilbobthebob, inertial, 1138",
    "version": (0, 0, 3, 5),
    "blender": (2, 93, 0),
    "category": "Import-Export"
}

if "bpy" in locals():
    import importlib
    importlib.reload(import_alo)
    importlib.reload(import_ala)
    importlib.reload(export_alo)
    importlib.reload(export_ala)
    importlib.reload(settings)
    importlib.reload(utils)
else:
    from . import import_alo
    from . import import_ala
    from . import export_alo
    from . import export_ala
    from . import settings
    from . import utils

def CheckObjectType(objects, type):
    for object in objects:
        if object.type != type:
            return False
    return True


def CheckPropAllSame(objects, prop):
    # True: All same, have value of True
    # False: All same, have value of False
    # None: Not all same
    first_value = None
    for object in objects:
        if first_value is None:
            first_value = getattr(object, prop)
        elif getattr(object, prop) != first_value:
            return None
    return first_value


def ShouldEnable(objects, prop, set_to):
    if objects is None or len(objects) <= 0:
        return False
    if bpy.context.mode == "OBJECT":
        objects_same = CheckObjectType(objects, "MESH")
        if not objects_same:
            return False
    all_same = CheckPropAllSame(objects, prop)
    if all_same is not None:
        if set_to:
            return not all_same
        else:
            return all_same
    return True


def ShouldEnableAnim(bones, prop, set_to):
    if bones is None or len(bones) <= 0:
        return False

    frame = bpy.context.scene.frame_current
    action = bpy.context.object.animation_data.action
    has_keyframes = False
    has_previous_keyframe = False
    for bone in bones:
        keyframes = action.fcurves.find(bone.path_from_id() + "." + prop)
        if keyframes is not None:
            for keyframe in keyframes.keyframe_points:
                if int(keyframe.co[0]) <= frame:
                    has_previous_keyframe = True
                if int(keyframe.co[0]) == frame:
                    has_keyframes = True
                    break

    if set_to is None:
        return has_keyframes    
    if not has_previous_keyframe:
        return True

    all_same = CheckPropAllSame(bones, prop)
    if all_same is not None:
        if set_to:
            return not all_same
        return all_same
    return True


class ValidateFileButton(bpy.types.Operator):
    bl_idname = "alamo.validate_file"
    bl_label = "Validate"

    def execute(self, context):
        mesh_list = validation.create_export_list(bpy.context.scene.collection, True, "DATA")

        #check if export objects satisfy requirements (has material, UVs, ...)
        messages = validation.validate(mesh_list)

        if messages is not None and len(messages) > 0:
            for message in messages:
                self.report(*message)
        else:
            self.report({'INFO'}, 'ALAMO - Validation complete. No errors detected!')
        return {'FINISHED'}


# Legacy version, provided for the debug panel
class createConstraintBoneButton(bpy.types.Operator):
    bl_idname = "create.constraint_bone"
    bl_label = "Create constraint bone"

    def execute(self, context):
        object = bpy.context.view_layer.objects.active
        armature = utils.findArmature()

        bpy.context.view_layer.objects.active = armature
        utils.setModeToEdit()

        bone = armature.data.edit_bones.new(object.name)
        bone.tail = bone.head + mathutils.Vector((0, 0, 1))
        bone.matrix = object.matrix_world
        object.location = mathutils.Vector((0.0, 0.0, 0.0))
        object.rotation_euler = mathutils.Euler((0.0, 0.0, 0.0), 'XYZ')
        constraint = object.constraints.new('CHILD_OF')
        constraint.target = armature
        constraint.subtarget = bone.name

        utils.setModeToObject()
        bpy.context.view_layer.objects.active = object
        return {'FINISHED'}


class CreateConstraintBone(bpy.types.Operator):
    bl_idname = "alamo.create_constraint_bone"
    bl_label = "Create Constraint Bone"

    @classmethod
    def poll(cls, context):
        object = bpy.context.object
        if (
            type(object) != type(None)
            and object.type == 'MESH'
            and bpy.context.mode == 'OBJECT'
        ):
            armature = utils.findArmature()
            if armature is not None:
                hasChildConstraint = False
                for constraint in object.constraints:
                    if constraint.type == 'CHILD_OF':
                        hasChildConstraint = True
                if not hasChildConstraint:
                    return True
        return False

    def execute(self, context):
        object = bpy.context.view_layer.objects.active
        armature = utils.findArmature()

        bpy.context.view_layer.objects.active = armature
        utils.setModeToEdit()

        bone = armature.data.edit_bones.new(object.name)
        bone.tail = bone.head + mathutils.Vector((0, 0, 1))
        bone.matrix = object.matrix_world
        object.location = mathutils.Vector((0.0, 0.0, 0.0))
        object.rotation_euler = mathutils.Euler((0.0, 0.0, 0.0), 'XYZ')
        constraint = object.constraints.new('CHILD_OF')
        constraint.target = armature
        constraint.subtarget = bone.name

        utils.setModeToObject()
        bpy.context.view_layer.objects.active = object
        return {'FINISHED'}


class ClearChildOf(bpy.types.Operator):
    bl_idname = "alamo.clear_childof"
    bl_label = ""
    bl_description = "Clear inverse from all Child Of Constraints"

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        for obj in context.scene.objects:
            for con in obj.constraints:
                if con.type == 'CHILD_OF':
                    con.inverse_matrix.identity()
        return {'FINISHED'}


class SetHasCollisionTrue(bpy.types.Operator):
    bl_idname = "alamo.collision_true"
    bl_label = ""
    bl_description = "Set HasCollision to True for all selected objects"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_objects, "HasCollision", True)

    def execute(self, context):
        objs = bpy.context.selected_objects
        for obj in objs:
            obj.HasCollision = True
        return {'FINISHED'}


class SetHasCollisionFalse(bpy.types.Operator):
    bl_idname = "alamo.collision_false"
    bl_label = ""
    bl_description = "Set HasCollision to False for all selected objects"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_objects, "HasCollision", False)

    def execute(self, context):
        objs = bpy.context.selected_objects
        for obj in objs:
            obj.HasCollision = False
        return {'FINISHED'}


class SetHiddenTrue(bpy.types.Operator):
    bl_idname = "alamo.hidden_true"
    bl_label = ""
    bl_description = "Set Hidden to True for all selected objects"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_objects, "Hidden", True)

    def execute(self, context):
        objs = bpy.context.selected_objects
        for obj in objs:
            obj.Hidden = True
        return {'FINISHED'}


class SetHiddenFalse(bpy.types.Operator):
    bl_idname = "alamo.hidden_false"
    bl_label = ""
    bl_description = "Set Hidden to False for all selected objects"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_objects, "Hidden", False)

    def execute(self, context):
        objs = bpy.context.selected_objects
        for obj in objs:
            obj.Hidden = False
        return {'FINISHED'}


class SetBoneVisible(bpy.types.Operator):
    bl_idname = "alamo.bone_visible"
    bl_label = ""
    bl_description = "Set Visible to True for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_bones, "Visible", True)

    def execute(self, context):
        bones = bpy.context.selected_bones
        for bone in bones:
            bone.Visible = True
        return {'FINISHED'}


class SetBoneInvisible(bpy.types.Operator):
    bl_idname = "alamo.bone_invisible"
    bl_label = ""
    bl_description = "Set Visible to False for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_bones, "Visible", False)

    def execute(self, context):
        bones = bpy.context.selected_bones
        for bone in bones:
            bone.Visible = False
        return {'FINISHED'}


class SetAltDecreaseStayHiddenTrue(bpy.types.Operator):
    bl_idname = "alamo.alt_decrease_stay_hidden_true"
    bl_label = ""
    bl_description = "Set altDecreaseStayHidden to True for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_bones, "altDecreaseStayHidden", True)

    def execute(self, context):
        bones = bpy.context.selected_bones
        for bone in bones:
            bone.altDecreaseStayHidden = True
        return {'FINISHED'}


class SetAltDecreaseStayHiddenFalse(bpy.types.Operator):
    bl_idname = "alamo.alt_decrease_stay_hidden_false"
    bl_label = ""
    bl_description = "Set altDecreaseStayHidden to False for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_bones, "altDecreaseStayHidden", False)

    def execute(self, context):
        bones = bpy.context.selected_bones
        for bone in bones:
            bone.altDecreaseStayHidden = False
        return {'FINISHED'}


class EnableProxyFalse(bpy.types.Operator):
    bl_idname = "alamo.disable_proxy"
    bl_label = ""
    bl_description = "Set EnableProxy to False for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_bones, "EnableProxy", False)

    def execute(self, context):
        bones = bpy.context.selected_bones
        for bone in bones:
            bone.EnableProxy = False
        return {'FINISHED'}


class EnableProxyTrue(bpy.types.Operator):
    bl_idname = "alamo.enable_proxy"
    bl_label = ""
    bl_description = "Set EnableProxy to True for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_bones, "EnableProxy", True)

    def execute(self, context):
        bones = bpy.context.selected_bones
        for bone in bones:
            bone.EnableProxy = True
        return {'FINISHED'}


class ProxyShow(bpy.types.Operator):
    bl_idname = "alamo.show_proxy"
    bl_label = ""
    bl_description = "Set proxyIsHidden to False for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_bones, "proxyIsHidden", False)

    def execute(self, context):
        bones = bpy.context.selected_bones
        for bone in bones:
            bone.proxyIsHidden = False
        return {'FINISHED'}


class ProxyHide(bpy.types.Operator):
    bl_idname = "alamo.hide_proxy"
    bl_label = ""
    bl_description = "Set proxyIsHidden to True for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnable(bpy.context.selected_bones, "proxyIsHidden", True)

    def execute(self, context):
        bones = bpy.context.selected_bones
        for bone in bones:
            bone.proxyIsHidden = True
        return {'FINISHED'}


class CopyProxyNameToSelected(bpy.types.Operator):
    bl_idname = "alamo.copy_proxy_name"
    bl_label = ""
    bl_description = "Copy Proxy Name to Selected Bones"

    @classmethod
    def poll(cls, context):
        return bpy.context.selected_bones is not None and len(bpy.context.selected_bones) > 1

    def execute(self, context):
        bones = bpy.context.selected_bones
        name = bones[0].ProxyName
        for bone in bones:
            bone.ProxyName = name
        return {'FINISHED'}


class CopyProxyNameFromBone(bpy.types.Operator):
    bl_idname = "alamo.copy_proxy_name_from_bone"
    bl_label = ""
    bl_description = "Copy Proxy Name from Bone Name"

    @classmethod
    def poll(cls, context):
        return bpy.context.selected_bones is not None and len(bpy.context.selected_bones) > 0

    def execute(self, context):
        for bone in bpy.context.selected_bones:
            name = bone.name
            # remove Blender numeric suffix (.001, .002, ...)
            if name[-4:-3] == "." and name[-3:].isdigit():
                name = name[:-4]
            bone.ProxyName = name
        return {'FINISHED'}


def keyframeProxySet(operation):
    bones = bpy.context.selected_pose_bones
    action = bpy.context.object.animation_data.action
    frame = bpy.context.scene.frame_current
    keyframeType = ""

    for bone in bones:
        if operation == 'SHOW':
            bone.proxyIsHiddenAnimation = False
            keyframeType = 'JITTER'
        if operation == 'HIDE':
            bone.proxyIsHiddenAnimation = True
            keyframeType = 'EXTREME'

        if operation == 'REMOVE':
            bone.keyframe_delete(data_path="proxyIsHiddenAnimation")
        else:
            bone.keyframe_insert(data_path="proxyIsHiddenAnimation", group=bone.name)
            # for keyframe in action.fcurves.find(bone.path_from_id() + ".proxyIsHiddenAnimation").keyframe_points:
            #     if int(keyframe.co[0]) == frame:
            #         keyframe.type = keyframeType

    for area in bpy.context.screen.areas:
        if area.type == 'DOPESHEET_EDITOR':
            area.tag_redraw()


class keyframeProxyShow(bpy.types.Operator):
    bl_idname = "alamo.show_keyframe_proxy"
    bl_label = ""
    bl_description = "Create a keyframe and set proxyIsHiddenAnimation to False for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnableAnim(bpy.context.selected_pose_bones, "proxyIsHiddenAnimation", False)

    def execute(self, context):
        keyframeProxySet('SHOW')
        return {'FINISHED'}


class keyframeProxyHide(bpy.types.Operator):
    bl_idname = "alamo.hide_keyframe_proxy"
    bl_label = ""
    bl_description = "Create a keyframe and set proxyIsHiddenAnimation to True for all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnableAnim(bpy.context.selected_pose_bones, "proxyIsHiddenAnimation", True)

    def execute(self, context):
        keyframeProxySet('HIDE')
        return {'FINISHED'}


class keyframeProxyRemove(bpy.types.Operator):
    bl_idname = "alamo.remove_keyframe_proxy"
    bl_label = ""
    bl_description = "Remove active keyframes from all selected bones"

    @classmethod
    def poll(cls, context):
        return ShouldEnableAnim(bpy.context.selected_pose_bones, "proxyIsHiddenAnimation", None)

    def execute(self, context):
        keyframeProxySet('REMOVE')
        return {'FINISHED'}


def skeletonEnumCallback(scene, context):
    armatures = [('None', 'None', '', '', 0)]
    counter = 1
    for arm in bpy.data.objects:  # test if armature exists
        if arm.type == 'ARMATURE':
            armatures.append((arm.name, arm.name, '', '', counter))
            counter += 1

    return armatures


class skeletonEnumClass(PropertyGroup):
    skeletonEnum : EnumProperty(
        name = 'Active Skeleton',
        description = "skeleton that is exported",
        items = skeletonEnumCallback
    )


def rowbuilder(layout, label, operators, icons):
    row = layout.row(align=True)
    row.label(text=label)
    row.operator(operators[0], text="", icon=icons[0])
    row.operator(operators[1], text="", icon=icons[1])


class ALAMO_PT_ToolsPanel(bpy.types.Panel):

    bl_label = "Alamo Properties"
    bl_idname = "ALAMO_PT_ToolsPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"

    def draw(self, context):
        row = self.layout.row()
        row.operator("alamo.validate_file")
        row.scale_y = 3.0


class ALAMO_PT_ObjectPanel(bpy.types.Panel):

    bl_label = "Object Tools"
    bl_parent_id = 'ALAMO_PT_ToolsPanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"

    def draw(self, context):
        object = context.object
        layout = self.layout
        scene = context.scene
        layout.active = False
        if bpy.context.mode == "OBJECT":
            layout.active = True

        rowbuilder(layout, "Set HasCollision:", ["alamo.collision_true", "alamo.collision_false"], ["CHECKMARK", "X"])

        rowbuilder(layout, "Set Hidden:", ["alamo.hidden_false", "alamo.hidden_true"], ["HIDE_OFF", "HIDE_ON"])

        row = layout.row()
        row.operator(
            "alamo.clear_childof",
            text="Clear Child Of",
            icon="CONSTRAINT"
        )



class ALAMO_PT_ArmatureSettingsPanel(bpy.types.Panel):

    bl_label = "Armature Settings"
    bl_parent_id = 'ALAMO_PT_ToolsPanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"

    def draw(self, context):
        object = context.object
        layout = self.layout
        scene = context.scene
        # layout.active = False

        layout.prop(scene.ActiveSkeleton, 'skeletonEnum')

        layout.operator("alamo.create_constraint_bone")


class ALAMO_PT_EditBonePanel(bpy.types.Panel):

    bl_label = "Edit Bone Tools"
    bl_parent_id = 'ALAMO_PT_ToolsPanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"

    def draw(self, context):
        bones = bpy.context.selected_bones
        layout = self.layout
        col = layout.column()
        layout.active = False
        if bpy.context.mode == "EDIT_ARMATURE":
            layout.active = True

        rowbuilder(layout, "Set Bone Visibility:", ["alamo.bone_visible", "alamo.bone_invisible"], ["HIDE_OFF", "HIDE_ON"])

        row = col.row()
        row.enabled = False
        if bones is not None:
            if len(bones) == 1:
                row.prop(bones[0].billboardMode, "billboardMode")
                row.enabled = True
            else:
                row.label(text="billboardMode")
        else:
            row.label(text="billboardMode")


class ALAMO_PT_EditBoneSubPanel(bpy.types.Panel):

    bl_label = ""
    bl_parent_id = 'ALAMO_PT_EditBonePanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"
    bl_options = {"HEADER_LAYOUT_EXPAND"}

    def draw_header(self, context):
        layout = self.layout
        layout.active = False
        if bpy.context.mode == "EDIT_ARMATURE":
            layout.active = True

        rowbuilder(layout, "Set Proxy:", ["alamo.enable_proxy", "alamo.disable_proxy"], ["CHECKMARK", "X"])

    def draw(self, context):
        bones = bpy.context.selected_bones
        layout = self.layout

        all_same = True

        layout.active = False
        if bpy.context.mode == "EDIT_ARMATURE":
            layout.active = all_same

        if not all_same:
            layout.label(icon="ERROR", text="Inconsistent EnableProxy states.")
            layout.label(icon="BLANK1", text="Change selection or set EnableProxy.")

        rowbuilder(layout, "Set Proxy Visibility:", ["alamo.show_proxy", "alamo.hide_proxy"], ["HIDE_OFF", "HIDE_ON"])

        rowbuilder(layout, "Set altDecreaseStayHidden:", ["alamo.alt_decrease_stay_hidden_true", "alamo.alt_decrease_stay_hidden_false"], ["CHECKMARK", "X"])

        row = layout.row(align=True)
        row.enabled = False
        if bones is not None and len(bones) > 0:
            row.prop(bones[0], "ProxyName")
            row.operator('alamo.copy_proxy_name', text="", icon="DUPLICATE")
            row.operator('alamo.copy_proxy_name_from_bone', text="", icon="BONE_DATA")
            row.enabled = True
        else:
            row.label(text="ProxyName")


class ALAMO_PT_AnimationPanel(bpy.types.Panel):

    bl_label = "Animation"
    bl_parent_id = 'ALAMO_PT_ToolsPanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout
        layout.active = False
        if bpy.context.mode == "POSE":
            layout.active = True
        # layout.column().label(text="Keyframe Proxy Visibility:")
        row = layout.row(align=True)
        row.label(text="Keyframe Proxy Visibility:")
        row.operator('alamo.show_keyframe_proxy', text="",
                     icon="HIDE_OFF")
        row.operator('alamo.hide_keyframe_proxy', text="",
                     icon="HIDE_ON")
        row.operator('alamo.remove_keyframe_proxy', text="",
                     icon="X")


class ALAMO_PT_AnimationActionSubPanel(bpy.types.Panel):

    bl_label = "Action End Frames"
    bl_parent_id = 'ALAMO_PT_AnimationPanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout
        for action in bpy.data.actions:
            layout.prop(action, "AnimationEndFrame", text=action.name)


class ALAMO_PT_DebugPanel(bpy.types.Panel):

    bl_label = "Debug"
    bl_parent_id = 'ALAMO_PT_ToolsPanel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        object = context.object
        layout = self.layout
        scene = context.scene
        c = layout.column()

        c.prop(scene.ActiveSkeleton, 'skeletonEnum')

        if type(object) != type(None):
            if(object.type == 'MESH'):
                if bpy.context.mode == 'OBJECT':
                    c.prop(object, "HasCollision")
                    c.prop(object, "Hidden")

                    armature = utils.findArmature()
                    if armature != None:
                        hasChildConstraint = False
                        for constraint in object.constraints:
                            if constraint.type == 'CHILD_OF':
                                hasChildConstraint = True
                        if not hasChildConstraint:
                            self.layout.operator("create.constraint_bone", text = 'Create Constraint Bone')

            action = utils.getCurrentAction()
            if(action != None):
                c.prop(action, "AnimationEndFrame")


        bone = bpy.context.active_bone
        if type(bone) != type(None):
            if(type(bpy.context.active_bone ) is bpy.types.EditBone):
                c.prop(bone.billboardMode, "billboardMode")
                c.prop(bone, "Visible")
                c.prop(bone, "EnableProxy")
                if bone.EnableProxy:
                    c.prop(bone, "proxyIsHidden")
                    c.prop(bone, "altDecreaseStayHidden")
                    c.prop(bone, "ProxyName")

            elif (type(bpy.context.active_bone) is bpy.types.Bone and bpy.context.mode == 'POSE'):
                poseBone = object.pose.bones[bone.name]
                c.prop(poseBone, "proxyIsHiddenAnimation")


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

        if type(object) != type(None) and object.type == 'MESH':
            material = bpy.context.active_object.active_material
            if material is not None:
                # a None image is needed to represent not using a texture
                if 'None' not in bpy.data.images:
                    bpy.data.images.new(name='None', width=1, height=1)
                col.prop(material.shaderList, "shaderList")
                if material.shaderList.shaderList != 'alDefault.fx':
                    shader_props = settings.material_parameter_dict[material.shaderList.shaderList]
                    for shader_prop in shader_props:
                        # because contains() doesn't exist, apparently
                        if shader_prop.find('Texture') > -1:
                            layout.prop_search(material, shader_prop, bpy.data, "images")
                            # layout.template_ID(material, shader_prop, new="image.new", open="image.open")


class ALAMO_PT_materialPropertySubPanel(bpy.types.Panel):
    bl_label = "Additional Properties"
    bl_parent_id = "ALAMO_PT_materialPropertyPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        object = context.object
        layout = self.layout
        col = layout.column()

        if type(object) != type(None) and object.type == 'MESH':
            material = bpy.context.active_object.active_material
            if material is not None and material.shaderList.shaderList != 'alDefault.fx':
                shader_props = settings.material_parameter_dict[material.shaderList.shaderList]
                for shader_prop in shader_props:
                    # because contains() doesn't exist, apparently
                    if shader_prop.find('Texture') == -1:
                        col.prop(material, shader_prop)


class shaderListProperties(bpy.types.PropertyGroup):
    mode_options = [
        (shader_name, shader_name, '', '', index)
        for index, shader_name in enumerate(settings.material_parameter_dict)
    ]

    shaderList: bpy.props.EnumProperty(
        items=mode_options,
        description="Choose ingame Shader",
        default="alDefault.fx",
    )


class billboardListProperties(bpy.types.PropertyGroup):
    mode_options = [
        ("Disable", "Disable", 'Description WIP', '', 0),
        ("Parallel", "Parallel", 'Description WIP', '', 1),
        ("Face", "Face", 'Description WIP', '', 2),
        ("ZAxis View", "ZAxis View", 'Description WIP', '', 3),
        ("ZAxis Light", "ZAxis Light", 'Description WIP', '', 4),
        ("ZAxis Wind", "ZAxis Wind", 'Description WIP', '', 5),
        ("Sunlight Glow", "Sunlight Glow", 'Description WIP', '', 6),
        ("Sun", "Sun", 'Description WIP', '', 7),
    ]

    billboardMode: bpy.props.EnumProperty(
        items=mode_options,
        description="billboardMode",
        default="Disable",
    )


def proxy_name_update(self, context):
    if self.ProxyName != self.ProxyName.upper():  # prevents endless recursion
        self.ProxyName = self.ProxyName.upper()

# blender registration


def menu_func_import(self, context):
    self.layout.operator(import_alo.ALO_Importer.bl_idname,
                         text=".ALO Importer")
    self.layout.operator(import_ala.ALA_Importer.bl_idname,
                         text=".ALA Importer")


def menu_func_export(self, context):
    self.layout.operator(export_alo.ALO_Exporter.bl_idname,
                         text=".ALO Exporter")
    self.layout.operator(export_ala.ALA_Exporter.bl_idname,
                         text=".ALA Exporter")


classes = (
    skeletonEnumClass,
    billboardListProperties,
    shaderListProperties,
    ALO_Importer,
    ALA_Importer,
    ALO_Exporter,
    ALA_Exporter,
    ALAMO_PT_materialPropertyPanel,
    ALAMO_PT_materialPropertySubPanel,
    ValidateFileButton,
    CreateConstraintBone,
    createConstraintBoneButton,
    ClearChildOf,
    SetHasCollisionTrue,
    SetHasCollisionFalse,
    SetHiddenTrue,
    SetHiddenFalse,
    SetBoneVisible,
    SetBoneInvisible,
    SetAltDecreaseStayHiddenTrue,
    SetAltDecreaseStayHiddenFalse,
    EnableProxyFalse,
    EnableProxyTrue,
    ProxyShow,
    ProxyHide,
    CopyProxyNameToSelected,
    CopyProxyNameFromBone,
    keyframeProxyShow,
    keyframeProxyHide,
    keyframeProxyRemove,
    ALAMO_PT_ToolsPanel,
    ALAMO_PT_ObjectPanel,
    ALAMO_PT_ArmatureSettingsPanel,
    ALAMO_PT_EditBonePanel,
    ALAMO_PT_EditBoneSubPanel,
    ALAMO_PT_AnimationPanel,
    ALAMO_PT_AnimationActionSubPanel,
    ALAMO_PT_DebugPanel
)


def register():

    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    bpy.types.Scene.ActiveSkeleton = PointerProperty(type=skeletonEnumClass)
    bpy.types.Scene.modelFileName = StringProperty(name="")

    bpy.types.Action.AnimationEndFrame = IntProperty(default=24)

    bpy.types.EditBone.Visible = BoolProperty(default=True)
    bpy.types.EditBone.EnableProxy = BoolProperty()
    bpy.types.EditBone.proxyIsHidden = BoolProperty()
    bpy.types.PoseBone.proxyIsHiddenAnimation = BoolProperty()
    bpy.types.EditBone.altDecreaseStayHidden = BoolProperty()
    bpy.types.EditBone.ProxyName = StringProperty(update=proxy_name_update)
    bpy.types.EditBone.billboardMode = bpy.props.PointerProperty(
        type=billboardListProperties)

    bpy.types.Object.HasCollision = BoolProperty()
    bpy.types.Object.Hidden = BoolProperty()

    bpy.types.Material.BaseTexture = bpy.props.StringProperty(default='None')
    bpy.types.Material.DetailTexture = bpy.props.StringProperty(default='None')
    bpy.types.Material.NormalDetailTexture = bpy.props.StringProperty(
        default='None')
    bpy.types.Material.NormalTexture = bpy.props.StringProperty(default='None')
    bpy.types.Material.GlossTexture = bpy.props.StringProperty(default='None')
    bpy.types.Material.WaveTexture = bpy.props.StringProperty(default='None')
    bpy.types.Material.DistortionTexture = bpy.props.StringProperty(
        default='None')
    bpy.types.Material.CloudTexture = bpy.props.StringProperty(default='None')
    bpy.types.Material.CloudNormalTexture = bpy.props.StringProperty(
        default='None')

    bpy.types.Material.shaderList = bpy.props.PointerProperty(
        type=shaderListProperties)
    bpy.types.Material.Emissive = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(0, 0, 0, 0))
    bpy.types.Material.Diffuse = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(1, 1, 1, 0))
    bpy.types.Material.Specular = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(1, 1, 1, 0))
    bpy.types.Material.Shininess = bpy.props.FloatProperty(
        min=0, max=255, default=32)
    bpy.types.Material.Colorization = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(1, 1, 1, 0))
    bpy.types.Material.DebugColor = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(0, 1, 0, 0))
    bpy.types.Material.UVOffset = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(0, 0, 0, 0))
    bpy.types.Material.Color = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(1, 1, 1, 1))
    bpy.types.Material.UVScrollRate = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(0, 0, 0, 0))
    bpy.types.Material.DiffuseColor = bpy.props.FloatVectorProperty(
        min=0, max=1, size=3, default=(0.5, 0.5, 0.5))
    # shield shader properties
    bpy.types.Material.EdgeBrightness = bpy.props.FloatProperty(
        min=0, max=255, default=0.5)
    bpy.types.Material.BaseUVScale = bpy.props.FloatProperty(
        min=-255, max=255, default=1)
    bpy.types.Material.WaveUVScale = bpy.props.FloatProperty(
        min=-255, max=255, default=1)
    bpy.types.Material.DistortUVScale = bpy.props.FloatProperty(
        min=-255, max=255, default=1)
    bpy.types.Material.BaseUVScrollRate = bpy.props.FloatProperty(
        min=-255, max=255, default=-0.15)
    bpy.types.Material.WaveUVScrollRate = bpy.props.FloatProperty(
        min=-255, max=255, default=-0.15)
    bpy.types.Material.DistortUVScrollRate = bpy.props.FloatProperty(
        min=-255, max=255, default=-0.25)
    # tree properties
    bpy.types.Material.BendScale = bpy.props.FloatProperty(
        min=-255, max=255, default=0.4)
    # grass properties
    bpy.types.Material.Diffuse1 = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(1, 1, 1, 1))
    # skydome.fx properties
    bpy.types.Material.CloudScrollRate = bpy.props.FloatProperty(
        min=-255, max=255, default=0.001)
    bpy.types.Material.CloudScale = bpy.props.FloatProperty(
        min=-255, max=255, default=1)
    # nebula.fx properties
    bpy.types.Material.SFreq = bpy.props.FloatProperty(
        min=-255, max=255, default=0.002)
    bpy.types.Material.TFreq = bpy.props.FloatProperty(
        min=-255, max=255, default=0.005)
    bpy.types.Material.DistortionScale = bpy.props.FloatProperty(
        min=-255, max=255, default=1)
    # planet.fx properties
    bpy.types.Material.Atmosphere = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(0.5, 0.5, 0.5, 0.5))
    bpy.types.Material.CityColor = bpy.props.FloatVectorProperty(
        min=0, max=1, size=4, default=(0.5, 0.5, 0.5, 0.5))
    bpy.types.Material.AtmospherePower = bpy.props.FloatProperty(
        min=-255, max=255, default=1)
    # tryplanar mapping properties
    bpy.types.Material.MappingScale = bpy.props.FloatProperty(
        min=0, max=255, default=0.1)
    bpy.types.Material.BlendSharpness = bpy.props.FloatProperty(
        min=0, max=255, default=0.1)


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    bpy.types.Scene.ActiveSkeleton

    bpy.types.Action.AnimationEndFrame

    bpy.types.EditBone.Visible
    bpy.types.EditBone.EnableProxy
    bpy.types.EditBone.proxyIsHidden
    bpy.types.PoseBone.proxyIsHiddenAnimation
    bpy.types.EditBone.altDecreaseStayHidden
    bpy.types.EditBone.ProxyName
    bpy.types.EditBone.billboardMode

    bpy.types.Object.HasCollision
    bpy.types.Object.Hidden

    bpy.types.Material.BaseTexture
    bpy.types.Material.DetailTexture
    bpy.types.Material.NormalTexture
    bpy.types.Material.NormalDetailTexture
    bpy.types.Material.GlossTexture
    bpy.types.Material.WaveTexture
    bpy.types.Material.DistortionTexture
    bpy.types.Material.CloudTexture
    bpy.types.Material.CloudNormalTexture

    bpy.types.Material.shaderList
    bpy.types.Material.Emissive
    bpy.types.Material.Diffuse
    bpy.types.Material.Specular
    bpy.types.Material.Shininess
    bpy.types.Material.Colorization
    bpy.types.Material.DebugColor
    bpy.types.Material.UVOffset
    bpy.types.Material.Color
    bpy.types.Material.UVScrollRate
    bpy.types.Material.DiffuseColor
    # shield shader properties
    bpy.types.Material.EdgeBrightness
    bpy.types.Material.BaseUVScale
    bpy.types.Material.WaveUVScale
    bpy.types.Material.DistortUVScale
    bpy.types.Material.BaseUVScrollRate
    bpy.types.Material.WaveUVScrollRate
    bpy.types.Material.DistortUVScrollRate
    # tree properties
    bpy.types.Material.BendScale
    # grass properties
    bpy.types.Material.Diffuse1
    # skydome.fx properties
    bpy.types.Material.CloudScrollRate
    bpy.types.Material.CloudScale
    # nebula.fx properties
    bpy.types.Material.SFreq
    bpy.types.Material.TFreq
    bpy.types.Material.DistortionScale
    # planet.fx properties
    bpy.types.Material.Atmosphere
    bpy.types.Material.CityColor
    bpy.types.Material.AtmospherePower
    # tryplanar mapping properties
    bpy.types.Material.MappingScale
    bpy.types.Material.BlendSharpness


if __name__ == "__main__":
    register()
