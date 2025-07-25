# Type Gen

This filter generates a `.d.ts` file that contains all the relevant constants in your add-on.

**Requires the [gametests](https://github.com/Bedrock-OSS/regolith-filters/tree/master/gametests) filter to be installed.**

## Data

1. Entities - All entity identifiers
2. Items - All item identifiers
3. Blocks - All block identifiers
4. Sounds - All sound identifiers
5. LangKeys - Language keys between `## #sync` and `## #endsync` lines in `en_US.lang`
6. Structures - All structure identifiers
7. LootTables - All loot table paths
8. Particles - All particle identifiers

## Getting the Filter

Install with: `regolith install type_gen`. After that, you can place the filter into one of your profiles. For the best results, you should run this filter as a last filter in your profile.

```json
{
    "filter": "type_gen"
}
```

## Usage

After running the filter at least once, you can import the generated `.d.ts` file in your project.

```ts
import { Entities } from './Files.d';
import { Dimension } from '@minecraft/server';

function spawnExampleEntity(dimension: Dimension) {
    return dimension.spawnEntity(Entities.Example);
}
```

## Settings

```json
{
  "outputFile": "Files.d.ts"
}
```

### outputFile

The output file to write the generated `.d.ts` file to. Defaults to `Files.d.ts`.

## Changelog

### 1.4.0

Change the default output file to `Files.ts` instead of `Files.d.ts`. 
If an existing `Files.d.ts` file is present, the generated file will be named `Files.d.ts` instead for compatibility.

### 1.3.2

Fixed an issue where the filter would fail, when an entity had no properties.

### 1.3.1

Removed debug logging from the filter.

### 1.3.0

Added entity properties to the generated `.d.ts` file.

### 1.2.1

Improved generation of block state superset to support boolean and string states.

### 1.2.0

Add generating a superset of block states to the generated `.d.ts` file.

### 1.1.0

Add trimming of common prefix to the generated `.d.ts` file.

### 1.0.4

Improve lang file parsing to fix some issues with comments and empty lines.

### 1.0.3

Sort the enums alphabetically for better readability.

### 1.0.2

Use CRLF line endings in the generated `.d.ts` file instead of LF.

### 1.0.1

[#55](https://github.com/Bedrock-OSS/regolith-filters/pull/55) Fixed issue where the filter would create an infinite loop when editing files in watch mode by [@FrederoxDev](https://github.com/FrederoxDev)

### 1.0.0

The first release of Type Gen.
