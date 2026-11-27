import bpy
from . import settings, utils

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )
import struct
import mathutils
import math
from math import pi
from mathutils import Vector
from bpy.props import *
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy_extras import anim_utils
import sys
import os
import bmesh
from contextlib import contextmanager

@contextmanager
def disable_exception_traceback():
    """
    All traceback information is suppressed and only the exception type and value are printed
    Used to make user friendly errors
    """
    default_value = getattr(sys, "tracebacklimit", 1000)  # `1000` is a Python's default value
    sys.tracebacklimit = 0
    yield
    sys.tracebacklimit = default_value  # revert changes

def chunk_size(size):
            #high bit is used to determine if a chunk holds chunks or data
            #add 2147483648 instead of binary operation
            return size+2147483648

def get_relative_matrix(pose):
    """Pose matrix relative to the parent bone (or armature space for root bones)."""
    if pose.parent != None:
        return pose.parent.matrix.inverted() @ pose.matrix
    return pose.matrix

def get_relative_translation(pose):
    return get_relative_matrix(pose).decompose()[0]

def get_relative_rotation(pose):
    return get_relative_matrix(pose).decompose()[1]

# ---------------------------------------------------------------------------
# Per-frame sampling. These only read the current scene frame.
# ---------------------------------------------------------------------------

def sample_translations(translationList, armature):
    """Relative translation of every bone in translationList at the current frame."""
    return [get_relative_translation(armature.pose.bones[name]) for name in translationList]

def create_rotation_frame_data(rotationList, armature):
    """Packed rotation data of every bone in rotationList at the current frame."""
    chunk = b''
    for name in rotationList:
        rotation_relative = get_relative_rotation(armature.pose.bones[name])
        chunk += struct.pack("<h", int(round(rotation_relative[1] * 32767)))
        chunk += struct.pack("<h", int(round(rotation_relative[2] * 32767)))
        chunk += struct.pack("<h", int(round(rotation_relative[3] * 32767)))
        chunk += struct.pack("<h", int(round(rotation_relative[0] * 32767)))
    return chunk

def get_visibility_bit(armature, bone):
    """'1' if the bone is visible at the current frame, '0' otherwise."""
    pose = armature.pose.bones[bone.name]
    parentPose = armature.pose.bones[bone.parent.name] if bone.parent is not None else None
    if pose.proxyIsHiddenAnimation or (parentPose is not None and parentPose.proxyIsHiddenAnimation):
        return '0'
    return '1'

# ---------------------------------------------------------------------------
# Processing of the sampled data
# ---------------------------------------------------------------------------

def calculateTranslationOffset(bone, armature, translationList, translationSamples):
    # if the bone has no animated translation data the offset is the relative translation data at an arbitrary frame, first frame is used
    # (the scene must be at frame 0 when this is called)
    # if the bone has animated translation data, the offset is the minimum of every translation
    # this is necessary because the translation data is stored as unsigned shorts, so every relative motion has to be positive
    if bone.name not in translationList:
        return get_relative_translation(armature.pose.bones[bone.name])

    index = translationList.index(bone.name)
    minimum = [65535, 65535, 65535]
    for frameSamples in translationSamples:
        translation_relative = frameSamples[index]
        for axis in range(3):
            minimum[axis] = min(minimum[axis], translation_relative[axis])
    return mathutils.Vector(minimum)

def calculateTranslationScale(bone, translationOffset, translationList, translationSamples):
    if bone.name not in translationList:
        return mathutils.Vector((0, 0, 0))

    # search for maximum translation
    index = translationList.index(bone.name)
    maximum = [0, 0, 0]
    for frameSamples in translationSamples:
        translation_relative = frameSamples[index]
        for axis in range(3):
            distance = abs(translation_relative[axis] - translationOffset[axis])
            maximum[axis] = max(maximum[axis], distance)

    return mathutils.Vector([(m if m != 0 else 1) / 65535.0 for m in maximum])

def create_translation_frame_data(frameSamples, translationList, translationOffsets, translationScales):
    """Packed translation data for one frame's samples (as returned by sample_translations)."""
    chunk = b''
    for name, translation_relative in zip(translationList, frameSamples):
        offset = translationOffsets[name]
        scale = translationScales[name]
        chunk += struct.pack("<H", int((translation_relative[0] - offset[0]) / scale[0]))
        chunk += struct.pack("<H", int((translation_relative[1] - offset[1]) / scale[1]))
        chunk += struct.pack("<H", int((translation_relative[2] - offset[2]) / scale[2]))
    return chunk

def wrap_data_chunk(chunk_id, data):
    """Prefix data with a chunk header; empty data produces no chunk."""
    if len(data) == 0:
        return b''
    return chunk_id + struct.pack("<I", len(data)) + data

def create_translation_data(translationData):
    return wrap_data_chunk(b'\x0a\x10\x00\x00', translationData)

def create_rotation_data(rotationData):
    return wrap_data_chunk(b'\x09\x10\x00\x00', rotationData)

# ---------------------------------------------------------------------------

def enter_pose_mode(armature):
    # for animation data we have to go into pose mode
    utils.setModeToObject()

    # select the skeleton
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')  # enter pose mode

def create_animation():

    chunk = b''
    # get armature name
    armature = utils.findArmature()
    if armature == None:
        self.report({"WARNING"}, "No armature found!")
        return b''

    chunk += create_anim_info_chunk(armature)

    rotationList = []
    translationList = []

    anim_data = armature.animation_data

    if anim_data == None:
        return b''
    
    # v5.x animation system, get channel bag for action slot
    channelbag = anim_utils.action_get_channelbag_for_slot(anim_data.action, anim_data.action_slot)

    # iterate over every pose bone
    for pose in armature.pose.bones:
        # iterate over every fcurves data (keyframes)
        for curve in channelbag.fcurves:
            # by spliting and comparing the data path we know which bone has rotation/location keyframes
            if curve.data_path.split('"')[1] == pose.name and curve.data_path.split('"')[2] == '].location':
                if (not (pose.name in translationList)): translationList.append(pose.name)  # if list doesnt contaion bone name add it
            if curve.data_path.split('"')[1] == pose.name and curve.data_path.split('"')[2] in settings.rotation_curve_name:
                if (not (pose.name in rotationList)):
                    rotationList.append(pose.name)  # if list doesnt contaion bone name add it

    exportBones = [bone for bone in armature.data.bones if bone.name != "Root"]
    visibilityBones = [bone for bone in exportBones if has_visibility_data(armature, bone)]

    enter_pose_mode(armature)

    # single pass over every frame, collecting all per-frame data
    scene = bpy.context.scene
    animLength = utils.getCurrentAction().AnimationEndFrame

    translationSamples = []  # one list of relative translations per frame
    rotationData = b''
    visibilityBits = {bone.name: '' for bone in visibilityBones}

    for frame in range(animLength + 1):
        scene.frame_set(frame)
        translationSamples.append(sample_translations(translationList, armature))
        rotationData += create_rotation_frame_data(rotationList, armature)
        for bone in visibilityBones:
            visibilityBits[bone.name] += get_visibility_bit(armature, bone)

    scene.frame_set(0)  # set scene to first frame, needed for default rotation/translation

    translationOffsets = {}
    translationScales = {}
    for bone in exportBones:
        offset = calculateTranslationOffset(bone, armature, translationList, translationSamples)
        translationOffsets[bone.name] = offset
        translationScales[bone.name] = calculateTranslationScale(bone, offset, translationList, translationSamples)

    # add the bone data chunks for every bone
    for bone in exportBones:
        chunk += create_bone_data(bone, translationList, rotationList, armature,
                                  translationOffsets[bone.name], translationScales[bone.name],
                                  visibilityBits.get(bone.name))

    translationData = b''
    for frameSamples in translationSamples:
        translationData += create_translation_frame_data(frameSamples, translationList, translationOffsets, translationScales)

    chunk += create_translation_data(translationData)  # add translation data chunk
    chunk += create_rotation_data(rotationData)  # add rotation data chunk

    header = (b"\x00\x10\x00\00")
    header += struct.pack("<I", chunk_size(len(chunk))) # chunk size

    return header + chunk

def create_anim_info_chunk(armature):

    action = utils.getCurrentAction()
    animLength = action.AnimationEndFrame

    chunk = b'\x01\x04'  # mini chunk name and length
    chunk += struct.pack("<I", animLength + 1)  # number of animation frames

    chunk += b'\x02\x04'  # mini chunk length
    chunk += struct.pack("<f", 30)

    chunk += b'\x03\x04'  # mini chunk length
    chunk += struct.pack("<I", len(
        armature.data.bones))  # add number of bones

    locationTracks = 0  # number of bones with location keyframes
    rotationTracks = 0  # number of bones with rotation keyframes
    # calculate location and rotation block sizes
    # iterate over every pose bone
    for pose in armature.pose.bones:  # iterate over every bone
        anim_data = armature.animation_data
        if anim_data == None:
            raise RuntimeError('Warning: no animation data found')
        
        # v5.x animation system, get channel bag for action slot
        channelbag = anim_utils.action_get_channelbag_for_slot(anim_data.action, anim_data.action_slot)
        # iterate over every fcurves data (keyframes)
        for curve in channelbag.fcurves:
            # by spliting and comparing the data path we know which bone has rotation/location keyframes
            if curve.data_path.split('"')[1] == pose.name and curve.data_path.split('"')[2] == '].location':
                locationTracks += 1
            if curve.data_path.split('"')[1] == pose.name and curve.data_path.split('"')[
                2] == '].rotation_quaternion':
                rotationTracks += 1

    # add rotationBlockSize
    chunk += b'\x0b\x04'  # mini chunk name and length
    chunk += struct.pack("<I", rotationTracks)

    # add translationBlockSize
    chunk += b'\x0c\x04'  # mini chunk name and length
    chunk += struct.pack("<I", locationTracks)

    # addScaleBlockSize, scale not supported set to 0
    chunk += b'\x0d\x04'  # mini chunk name and length
    chunk += struct.pack("<I", 0)

    chunkHeader = (b"\x01\x10\x00\00")  # chunk header
    chunkHeader += struct.pack("<I", len(chunk))  # add length

    return chunkHeader + chunk

def create_bone_data(bone, translationList, rotationList, armature, translationOffset, translationScale, visibilityBits):
    chunk = create_bone_animation_info_chunk(bone, translationList, rotationList, armature, translationOffset, translationScale, visibilityBits)
    header = (b"\x02\x10\x00\00")
    header += struct.pack("<I", chunk_size(len(chunk))) # add length
    return header + chunk
    # add support for step key track

def create_bone_animation_info_chunk(bone, translationList, rotationList, armature, translationOffset, translationScale, visibilityBits):
    # expects the scene to be at frame 0 and in post mode
    pose = armature.pose.bones[bone.name]

    # default rotation is rotation of first frame
    default_rotation = get_relative_rotation(pose)

    chunk = b'\x04'  # mini chunk name
    name = utils.clean_name(bone.name)
    chunk += struct.pack("<B", (len(name) + 1))  # size of name
    chunk += bytes(name, 'utf-8') + b"\x00"  # add bone name

    chunk += b'\x05\x04'  # mini chunk name and length

    # get the index of the current bone
    counter = 1 #start at because we ignore root bone
    for b in armature.data.bones:
        if (bone.name == b.name):
            index = counter
            break
        counter += 1
    chunk += struct.pack("<i", index)  # index of bone

    chunk += b'\x0a\x04'  # mini chunk name and length
    chunk += b'\x00\x00\00\00'  # unknown chunk

    chunk += b'\x06\x0c'  # mini chunk name and length
    # translation offset, is the location at the first frame, relative to the parent
    chunk += struct.pack("<f", translationOffset[0])
    chunk += struct.pack("<f", translationOffset[1])
    chunk += struct.pack("<f", translationOffset[2])

    chunk += b'\x07\x0c'  # mini chunk name and length
    # translation scale
    chunk += struct.pack("<f", translationScale[0])
    chunk += struct.pack("<f", translationScale[1])
    chunk += struct.pack("<f", translationScale[2])

    chunk += b'\x08\x0c'  # mini chunk name and length
    # scale offset, just 1 for now
    chunk += struct.pack("<f", 1)
    chunk += struct.pack("<f", 1)
    chunk += struct.pack("<f", 1)

    chunk += b'\x09\x0c'  # mini chunk name and length
    # scale scale, just 1 for now
    chunk += struct.pack("<f", 1)
    chunk += struct.pack("<f", 1)
    chunk += struct.pack("<f", 1)

    # add translation index
    chunk += b'\x0e\x02'  # mini chunk name and length
    if (bone.name in translationList):
        translationIndex = translationList.index(bone.name) * 3  # if bone is in location list use index in list as index
    else:
        translationIndex = -1  # if bone is not in location list use -1
    chunk += struct.pack("<h", translationIndex)

    # add scale index
    chunk += b'\x0f\x02'  # mini chunk name and length
    chunk += struct.pack("<h", -1)  # scale index, scale not implemented

    # add rotation index
    chunk += b'\x10\x02'  # mini chunk name and length
    if (bone.name in rotationList):
        rotationIndex = 4 * rotationList.index(
            bone.name)  # if bone is in rotation list use index in list as index
    else:
        rotationIndex = -1  # if bone is not in rotation list use -1

    chunk += struct.pack("<h", rotationIndex)

    # add default rotation
    chunk += b'\x11\x08'  # mini chunk name and length

    chunk += struct.pack("<h", int(default_rotation[1] * 32767))
    chunk += struct.pack("<h", int(default_rotation[2] * 32767))
    chunk += struct.pack("<h", int(default_rotation[3] * 32767))
    chunk += struct.pack("<h", int(default_rotation[0] * 32767))

    header = (b"\x03\x10\x00\00")
    header += struct.pack("<I", len(chunk))  # add length

    chunk = header + chunk

    visibility_chunk = create_visibility_chunk(visibilityBits)

    return chunk + visibility_chunk

def has_visibility_data(armature, bone):
    channelbag = anim_utils.action_get_channelbag_for_slot(armature.animation_data.action, armature.animation_data.action_slot)
    for curve in channelbag.fcurves:
        # by spliting and comparing the data path we know which bone has visibility keyframes
        parts = curve.data_path.split('"')
        if (parts[2] == '].proxyIsHiddenAnimation'):
            if parts[1] == bone.name or (bone.parent is not None and bone.parent.name == parts[1]):
                return True
    return False

def create_visibility_chunk(binary):
    """binary: string of '0'/'1' per frame, or None if the bone has no visibility data."""
    if binary is None:
        return b''

    while len(binary)%8 != 0:
        binary += '0'

    chunk = b''

    while len(binary) > 1:
        binaryReverse = binary[0:8][::-1] #file is little endian, reverse byte
        int_value = int(binaryReverse, 2)
        chunk += struct.pack('<B', int_value)
        binary = binary[8:]
    chunkHeader = b'\x07\x10\x00\00'
    chunkHeader += struct.pack('<I', len(chunk))
    return chunkHeader + chunk

class AnimationExporter():

    def exportAnimation(self, path):
        if os.access(path, os.W_OK) or not os.access(path, os.F_OK):
            file = open(path, 'wb')  # open file in read binary mode
            file.write(create_animation())
            file.close()
            file = None
        else:
            with disable_exception_traceback():
                raise Exception(f"ALAMO - EXPORT FAILED; can't write {os.path.split(path)[1]}")

class ALA_Exporter(bpy.types.Operator):

    """ALA Exporter"""  # blender will use this as a tooltip for menu items and buttons.
    bl_idname = "export_anim.ala"  # unique identifier for buttons and menu items to reference.
    bl_label = "Export ALA File"  # display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # enable undo for the operator.
    bl_info = {
        "name": "ALA Exporter",
        "category": "Export",
    }
    filename_ext = ".ala"
    filter_glob : StringProperty(default="*.ala", options={'HIDDEN'})

    filepath : StringProperty(name="File Path", description="Filepath used for exporting the ALO file", maxlen=1024,
                              default="")


    def execute(self, context):

        path = self.properties.filepath

        exporter = AnimationExporter()
        exporter.exportAnimation(path)

        return {'FINISHED'}  # this lets blender know the operator finished successfully.

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
