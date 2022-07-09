# texture_list

This filter automatically creates `texture_list.json` for you, so you don't need to! To learn more about this file, you can read our [wiki article](https://wiki.bedrock.dev/visuals/textures-list.html#top).

In a nutshell, this file makes Minecraft more efficient, by caching where textures are located. In some versions of Minecraft, failing to create this file actually results in a content log. Letting Regolith generate this file for you is the easiest way to ensure MC stays fast, and content-log-free.

This filter also supports subpacks.

## Using this Filter

First, ensure that you have [python installed.](https://bedrock-oss.github.io/regolith/docs/python-filters)!

Then, run `regolith install texture_list`, to install the filter into your project.

Finally, add this filter into the profile of your choice:

```json
{
	"filter": "texture_list"
}
```

## Example Project

An example project for this filter is contained within the `tests` folder of this repository. It contains a few nested textures, of different types.

# Changelog

## 1.0.0

The first release of `texture_list`.

## 1.1.0

 - Adds support for [subpacks](https://wiki.bedrock.dev/concepts/subpacks.html#top).

### 1.1.1

 - Fixes issues where resource packs without `subpack` folder would crash during compilation.

### 1.1.2

 - Fixes issue where subpacks without a 'texture' folder would crash.