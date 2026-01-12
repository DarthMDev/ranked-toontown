def px_to_scale(asset_width, asset_height, window_width=1920, window_height=1080):

    aspect_ratio = window_width/window_height
    x_scale = (asset_width/window_width) * (2.0 * aspect_ratio)
    z_scale = (asset_height/window_height) * 2.0

    return (x_scale, 1, z_scale)

def fontpx_to_scale(asset_width, asset_height, window_width=1920, window_height=1080): #yeah ok panda3d

    aspect_ratio = window_width/window_height
    x_scale = (asset_width/window_width) * (2.0 * aspect_ratio)
    z_scale = (asset_height/window_height) * 2.0

    return (x_scale, z_scale, 1)

def coords_to_pos(x_coord, z_coord, window_width=1920, window_height=1080):

    aspect_ratio = window_width/window_height
    x_panda = ((x_coord/window_width) * (2.0 * aspect_ratio)) - aspect_ratio
    z_panda = 1.0 - ((z_coord/window_height) * 2.0)

    return (x_panda, 0, z_panda)

print(px_to_scale(18, 13.8462, 308, 24))
print(coords_to_pos(260.128, 0, 308, 24))