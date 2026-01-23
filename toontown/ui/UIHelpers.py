def px_to_scale(asset_width, asset_height, window_width=1920, window_height=1080):

    aspect_ratio = window_width/window_height
    x_scale = (asset_width/window_width) * (2.0 * aspect_ratio)
    z_scale = (asset_height/window_height) * 2.0

    return (x_scale, 1, z_scale)

def coords_to_pos(x_coord, z_coord, window_width=1920, window_height=1080):

    aspect_ratio = window_width/window_height
    x_panda = ((x_coord/window_width) * (2.0 * aspect_ratio)) - aspect_ratio
    z_panda = 1.0 - ((z_coord/window_height) * 2.0)

    return (x_panda, 0, z_panda)

def coords_to_a2dRightCenter_pos(x_coord, z_coord, window_width=1920, window_height=1080):
    #calculate midpoint and aspect ratio
    x_canvas_midpoint = window_width/2.0
    aspect_ratio = window_width/window_height

    #find x coord, subtract by midpoint because we're placing on the right side of the window,
    #then divide by canvas midpoint to find the %. subtract it from 1 then mult by aspect ratio/window size whatever
    x_panda = (1.0 - ((x_coord - x_canvas_midpoint)/x_canvas_midpoint)) * aspect_ratio

    #z remains the same because it is parented to a center already (i think) but if i make methods for corners just use those instead
    z_panda = 1.0 - ((z_coord/window_height) * 2.0)

    #okay lowkey this might not even needed, just place it wherever and wrtReparentTo, might matter for backing/boilerplate/whatever

    return (-x_panda, 0, z_panda)