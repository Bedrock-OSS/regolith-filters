const glob = require("glob");
const fs = require("fs");

glob("RP/models/**/*.bbmodel", null, function (er, files) {
  files.forEach(function (file) {
    fs.readFile(file, "utf8", function (err, data) {
      let resultName = file.substr(0, file.lastIndexOf(".")) + ".json";
      console.log("Converting " + file + " into " + resultName);
      fs.writeFileSync(
        resultName,
        exportModel(JSON.parse(data))
        );
      fs.unlinkSync(file);
    });
  });
});

glob("RP/models/**/*.entity.bbmodel", null, function (er, files) {
  files.forEach(function (file) {
    fs.readFile(file, "utf8", function (err, data) {
      let resultName = file.substr(0, file.lastIndexOf(".")) + ".png";
      console.log("Converting " + file + " into " + resultName);
      exportTexture(JSON.parse(data), "entity");
    });
  });
});

glob("RP/models/**/*.block.bbmodel", null, function (er, files) {
  files.forEach(function (file) {
    fs.readFile(file, "utf8", function (err, data) {
      let resultName = file.substr(0, file.lastIndexOf(".")) + ".png";
      console.log("Converting " + file + " into " + resultName);
      exportTexture(JSON.parse(data), "blocks");
    });
  });
});

function exportTexture(data, mType) {
  try {
    for (let t = 0; t < data["textures"].length; t++) {
      let textureName = data["textures"][t]["name"];
      let textureData = data["textures"][t]["source"].replace("data:image/png;base64,", "");
      if (fs.existsSync("RP/textures/" + mType + "/") == false) {
        fs.mkdirSync("RP/textures/" + mType + "/");
      }
      fs.writeFileSync("RP/textures/" + mType + "/" + textureName + ".png", textureData, "base64");
  }
} catch {
    console.log("No textures found");
  }
}

// From: https://github.com/bridge-core/editor/blob/main/src/components/ImportFile/BBModel.ts

// From: https://github.com/JannisX11/blockbench/blob/1701f764641376414d29100c4f6c7cd74997fad8/js/io/formats/bedrock.js#L652
function exportModel(data) {
  let entitymodel = {};
  let main_tag = {
    format_version: "1.12.0",
    "minecraft:geometry": [entitymodel],
  };
  entitymodel.description = {
    identifier: "geometry." + (data.geometry_name || "unknown"),
    texture_width: data.resolution.width || 16,
    texture_height: data.resolution.height || 16,
  };
  let bones = [];

  let groups = getAllGroups(data);
  groups.forEach((group) => {
    let bone = compileGroup(data, group);
    bones.push(bone);
  });

  if (bones.length) {
    let visible_box = calculateVisibleBox(data);
    entitymodel.description.visible_bounds_width = visible_box[0] || 0;
    entitymodel.description.visible_bounds_height = visible_box[1] || 0;
    entitymodel.description.visible_bounds_offset = [0, visible_box[2] || 0, 0];

    entitymodel.bones = bones;
  }

  return compileJSON(main_tag);
}

//From: https://github.com/JannisX11/blockbench/blob/1701f764641376414d29100c4f6c7cd74997fad8/js/outliner/group.js#L492
function getAllGroups(data) {
  let groups = [];

  function iterate(array, parent) {
    for (let obj of array) {
      if (obj instanceof Object) {
        obj.parent = parent;
        groups.push(obj);
        iterate(obj.children, obj.name);
      }
    }
  }

  iterate(data.outliner, undefined);
  return groups;
}

//From: https://github.com/JannisX11/blockbench/blob/1701f764641376414d29100c4f6c7cd74997fad8/js/io/formats/bedrock.js#L571
function compileGroup(data, group) {
  let bone = {};
  bone.name = group.name;
  bone.parent = group.parent;
  bone.pivot = group.origin.slice();
  bone.pivot[0] *= -1;
  if (group.rotation) {
    if (
      group.rotation[0] !== 0 ||
      group.rotation[1] !== 0 ||
      group.rotation[2] !== 0
    ) {
      bone.rotation = group.rotation.slice();
      bone.rotation[0] *= -1;
      bone.rotation[1] *= -1;
    }
  }
  if (group.bedrock_binding) {
    bone.binding = group.bedrock_binding;
  }
  if (group.reset) {
    bone.reset = true;
  }
  if (group.mirror_uv && data.meta.box_uv) {
    bone.mirror = true;
  }
  if (group.material) {
    bone.material = group.material;
  }

  let cubes = [];
  let locators = {};

  for (let child of group.children) {
    if (!(child instanceof Object)) {
      let element = data.elements.find((element) => element.uuid === child);
      if (element.type !== "locator") {
        let cube = compileCube(data, element, bone);
        cubes.push(cube);
      } else if (element.type === "locator") {
        let key = element.name;
        let offset = element.from.slice();
        offset[0] *= -1;

        if (
          element.rotation[0] !== 0 ||
          element.rotation[1] !== 0 ||
          element.rotation[2] !== 0
        ) {
          locators[key] = {
            offset,
            rotation: [
              -element.rotation[0],
              -element.rotation[0],
              element.rotation[0],
            ],
          };
        } else {
          locators[key] = offset;
        }
      }
    }
  }

  if (cubes.length) {
    bone.cubes = cubes;
  }
  if (Object.keys(locators).length) {
    bone.locators = locators;
  }
  return bone;
}

//From: https://github.com/JannisX11/blockbench/blob/1701f764641376414d29100c4f6c7cd74997fad8/js/io/formats/bedrock.js#L516
function compileCube(data, element, bone) {
  let cube = {
    origin: element.from ? element.from.slice() : undefined,
    size: [
      element.to[0] - element.from[0],
      element.to[1] - element.from[1],
      element.to[2] - element.from[2],
    ],
    inflate: element.inflate || undefined,
  };
  cube.origin[0] = -(cube.origin[0] + cube.size[0]);

  if (element.rotation) {
    if (
      element.rotation[0] !== 0 ||
      element.rotation[1] !== 0 ||
      element.rotation[2] !== 0
    ) {
      cube.pivot = element.origin.slice();
      cube.pivot[0] *= -1;

      cube.rotation = element.rotation.slice();
      cube.rotation.forEach(function (br, axis) {
        if (axis !== 2) cube.rotation[axis] *= -1;
      });
    }
  }

  if (data.meta.box_uv) {
    cube.uv = element.uv_offset;
    if (element.mirror_uv === !bone.mirror) {
      cube.mirror = element.mirror_uv;
    }
  } else {
    cube.uv = {};
    for (let key in element.faces) {
      let face = element.faces[key];
      if (face.texture !== null) {
        cube.uv[key] = {
          uv: [face.uv[0], face.uv[1]],
          uv_size: [face.uv[2] - face.uv[0], face.uv[3] - face.uv[1]],
        };
        if (face.material_name) {
          cube.uv[key].material_instance = face.material_name;
        }
        if (key === "up" || key === "down") {
          cube.uv[key].uv[0] += cube.uv[key].uv_size[0];
          cube.uv[key].uv[1] += cube.uv[key].uv_size[1];
          cube.uv[key].uv_size[0] *= -1;
          cube.uv[key].uv_size[1] *= -1;
        }
      }
    }
  }
  return cube;
}

//From: https://github.com/JannisX11/blockbench/blob/1701f764641376414d29100c4f6c7cd74997fad8/js/io/formats/bedrock.js#L276
function calculateVisibleBox(data) {
  let visible_box = {
    max: {
      x: 0,
      y: 0,
      z: 0,
    },
    min: {
      x: 0,
      y: 0,
      z: 0,
    },
  };

  const elements = data.elements;
  elements.forEach((element) => {
    if (!element.to || !element.from) return;

    visible_box.max.x = Math.max(
      visible_box.max.x,
      element.from[0],
      element.to[0]
    );
    visible_box.min.x = Math.min(
      visible_box.min.x,
      element.from[0],
      element.to[0]
    );

    visible_box.max.y = Math.max(
      visible_box.max.y,
      element.from[1],
      element.to[1]
    );
    visible_box.min.y = Math.min(
      visible_box.min.y,
      element.from[1],
      element.to[1]
    );

    visible_box.max.z = Math.max(
      visible_box.max.z,
      element.from[2],
      element.to[2]
    );
    visible_box.min.z = Math.min(
      visible_box.min.z,
      element.from[2],
      element.to[2]
    );
  });

  visible_box.max.x += 8;
  visible_box.min.x += 8;
  visible_box.max.y += 8;
  visible_box.min.y += 8;
  visible_box.max.z += 8;
  visible_box.min.z += 8;

  //Width
  let radius = Math.max(
    visible_box.max.x,
    visible_box.max.z,
    -visible_box.min.x,
    -visible_box.min.z
  );
  if (Math.abs(radius) === Infinity) {
    radius = 0;
  }
  let width = Math.ceil((radius * 2) / 16);
  width = Math.max(width, data.visible_box[0]);

  //Height
  let y_min = Math.floor(visible_box.min.y / 16);
  let y_max = Math.ceil(visible_box.max.y / 16);
  if (y_min === Infinity) y_min = 0;
  if (y_max === Infinity) y_max = 0;
  y_min = Math.min(y_min, data.visible_box[2] - data.visible_box[1] / 2);
  y_max = Math.max(y_max, data.visible_box[2] + data.visible_box[1] / 2);

  return [width, y_max - y_min, (y_max + y_min) / 2];
}

// From: https://github.com/JannisX11/blockbench/blob/914e7eb1f74232c1a31ccf278c793309bb163848/js/io/io.js#L328
function compileJSON(object, options) {
  if (typeof options !== "object") options = {};
  function newLine(tabs) {
    if (options.small === true) {
      return "";
    }
    var s = "\n";
    for (var i = 0; i < tabs; i++) {
      s += "\t";
    }
    return s;
  }
  function escape(string) {
    return string
      .replace(/\\/g, "\\\\")
      .replace(/"/g, '\\"')
      .replace(/\n|\r\n/g, "\\n")
      .replace(/\t/g, "\\t");
  }
  function handleVar(o, tabs) {
    var out = "";
    if (typeof o === "string") {
      //String
      out += '"' + escape(o) + '"';
    } else if (typeof o === "boolean") {
      //Boolean
      out += o ? "true" : "false";
    } else if (o === null || o === Infinity || o === -Infinity) {
      //Null
      out += "null";
    } else if (typeof o === "number") {
      //Number
      o = (Math.round(o * 100000) / 100000).toString();
      out += o;
    } else if (typeof o === "object" && o instanceof Array) {
      //Array
      var has_content = false;
      out += "[";
      for (var i = 0; i < o.length; i++) {
        var compiled = handleVar(o[i], tabs + 1);
        if (compiled) {
          var breaks = typeof o[i] === "object";
          if (has_content) {
            out += "," + (breaks || options.small ? "" : " ");
          }
          if (breaks) {
            out += newLine(tabs);
          }
          out += compiled;
          has_content = true;
        }
      }
      if (typeof o[o.length - 1] === "object") {
        out += newLine(tabs - 1);
      }
      out += "]";
    } else if (typeof o === "object") {
      //Object
      var breaks = o.constructor.name !== "oneLiner";
      var has_content = false;
      out += "{";
      for (var key in o) {
        if (o.hasOwnProperty(key)) {
          var compiled = handleVar(o[key], tabs + 1);
          if (compiled) {
            if (has_content) {
              out += "," + (breaks || options.small ? "" : " ");
            }
            if (breaks) {
              out += newLine(tabs);
            }
            out +=
              '"' + escape(key) + '":' + (options.small === true ? "" : " ");
            out += compiled;
            has_content = true;
          }
        }
      }
      if (breaks && has_content) {
        out += newLine(tabs - 1);
      }
      out += "}";
    }
    return out;
  }
  return handleVar(object, 1);
}