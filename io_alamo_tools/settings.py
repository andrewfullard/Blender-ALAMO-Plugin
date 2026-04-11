import bpy

# Lists material parameters
material_parameter_list = []
# Lists what parameters a material has
material_parameter_dict = {
	"alDefault.fx": [""],
}
vertex_format_dict = {
    "alDefault.fx"          : "alD3dVertNU2",
}

billboard_array = {"Disable":0, "Parallel":1, "Face":2, "ZAxis View": 3, "ZAxis Light":4, "ZAxis Wind":5, "Sunlight Glow":6, "Sun":7}

#bumpMappingList = ['MeshBumpColorize.fx', 'MeshBumpReflectColorize.fx', 'MeshBumpColorizeVertex.fx', 'MeshBumpColorizeDetail.fx', "MeshBumpLight.fx", "Planet.fx", "RSkinBumpColorize.fx", "TerrainMeshBump.fx", "Tree.fx", "MeshBumpSpecColorize.fx", "MeshBumpColorizeTile.fx"]
bumpMappingList = []
rotation_curve_name = ['].rotation_quaternion', '].rotation_euler']

#no_UV_Shaders = {"alDefault.fx", "MeshCollision.fx", "MeshShadowVolume.fx", "RSkinShadowVolume.fx"}
