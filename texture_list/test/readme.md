# Texture List Tests

This folder contains a test project for the texture list filter.

## Running Tests

To run tests, you may navigate into this folder, and run `regolith run test`. The output should be viewable inside of `build` folder, which isn't checked into src control.

## Explanation

This test-setup will show how the texture_list.json files are created, in relation to main textures, and subpacks. 

`pack1` shows a subpack with the same set of textures, effectively overriding those in the main folder. This means it's `texture_list.json` file will be the same as the main pack.

`pack2` contains a new texture, which wasn't there in the main pack. In this case, the `texture_list.json` file will contain this new texture, along with the textures defined in the main pack. 

The logic is essentially: When the subpack is enabled, it will replace all files, including `texture_list.json`. Thus, the file contained in each subpack needs to list textures used within itself, as well as those contained outside. 

The `texture_list.json` file in the main pack is required, because a subpack may not contain any textures, and thus no `texture_list.json` file.