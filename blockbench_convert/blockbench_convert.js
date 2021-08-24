const glob = require("glob");
const fs = require("fs");

console.warn("This filter is still WIP");

glob("RP/models/**/*.bbmodel", null, function (er, files) {
  files.forEach(function (file) {
    fs.readFile(file, "utf8", function (err, data) {
      fs.writeFileSync(file.substr(0, file.lastIndexOf('.')) + ".json", parseBBModel(data));
    });
  });
});

function parseBBModel(data) {
  let model = JSON.parse(data);

  var entitymodel = {};
  var main_tag = {
    format_version: model.outliner.find((group) => group.bedrock_binding)
      ? "1.16.0"
      : "1.12.0",
    "minecraft:geometry": [entitymodel],
  };
  entitymodel.description = {
    identifier: "geometry." + (model.geometry_name || "unknown"),
    texture_width: model.resolution.width || 16,
    texture_height: model.resolution.height || 16,
  };
  // Make a map of UUID -> Element/Group
  let all = {};
  model.outliner.forEach((x) => {
    all[x.uuid] = x;
  });
  model.elements.forEach((x) => {
    all[x.uuid] = x;
  });
  // Add parent link
  model.outliner.forEach((x) => {
    if (x.children) {
      x.children.forEach((c) => {
        all[c].parent = x.uuid;
      });
    }
  });

  var bones = [];

  var groups = model.outliner;
  // Collect loose elements and group into bb_main group
  var loose_elements = [];
  model.elements.forEach((obj) => {
    if (!obj.parent) {
      loose_elements.push(obj.uuid);
      obj.parent = "bb_main";
    }
  });
  if (loose_elements.length) {
    let group = {
      name: "bb_main",
      origin: [0, 0, 0],
      export: true,
      children: loose_elements,
    };
    all.bb_main = group;
    groups.splice(0, 0, group);
  }

  groups.forEach(function (g) {
    if (!g.uuid) return;
    let bone = compileGroup(g, all, model.meta.box_uv);
    bones.push(bone);
  });

  // if (bones.length && options.visible_box !== false) {
  //   let visible_box = calculateVisibleBox();
  //   entitymodel.description.visible_bounds_width = visible_box[0] || 0;
  //   entitymodel.description.visible_bounds_height = visible_box[1] || 0;
  //   entitymodel.description.visible_bounds_offset = [0, visible_box[2] || 0, 0];
  // }
  if (bones.length) {
    entitymodel.bones = bones;
  }

  return compileJSON(main_tag);
}

function compileGroup(g, all, box_uv) {
  //Bone
  var bone = {};
  bone.name = g.name;
  if (g.parent) {
    bone.parent = all[g.parent].name;
  }
  bone.pivot = (g.origin ?? [0, 0, 0]).slice();
  bone.pivot[0] *= -1;
  if (g.rotation && !allEqual0(g.rotation)) {
    bone.rotation = g.rotation.slice();
    bone.rotation[0] *= -1;
    bone.rotation[1] *= -1;
  }
  if (g.bedrock_binding) {
    bone.binding = g.bedrock_binding;
  }
  // TODO: No clue what's that
  // if (g.reset) {
  //   bone.reset = true;
  // }
  // if (g.mirror_uv && Project.box_uv) {
  //   bone.mirror = true;
  // }
  // if (g.material) {
  //   bone.material = g.material;
  // }
  //Cubes
  var cubes = [];
  var locators = {};

  for (var c of g.children ?? []) {
    let obj = all[c];
    if (obj.export || obj.export === void 0) {
      if (!obj.children && obj.type !== "locator") {
        let template = compileCube(obj, bone, box_uv);
        cubes.push(template);
      } else if (obj.type && obj.type === "locator") {
        let key = obj.name;
        let offset = obj.from.slice();
        offset[0] *= -1;

        if (obj.rotation && !allEqual0(obj.rotation)) {
          locators[key] = {
            offset,
            rotation: [-obj.rotation[0], -obj.rotation[0], obj.rotation[0]],
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

function compileCube(obj, bone, box_uv) {
  var template = {
    origin: obj.from.slice(),
    size: cubeSize(obj),
    // TODO: No clue what's that
    inflate: obj.inflate || undefined,
  };
  if (box_uv) {
    template = new oneLiner(template);
  }
  template.origin[0] = -(template.origin[0] + template.size[0]);

  if (obj.rotation && !allEqual0(obj.rotation)) {
    template.pivot = obj.origin.slice();
    template.pivot[0] *= -1;

    template.rotation = obj.rotation.slice();
    template.rotation.forEach(function (br, axis) {
      if (axis != 2) template.rotation[axis] *= -1;
    });
  }

  if (box_uv) {
    template.uv = obj.uv_offset;
    // TODO: No clue what's that
    // if (obj.mirror_uv === !bone.mirror) {
    //   template.mirror = obj.mirror_uv;
    // }
  } else {
    template.uv = {};
    for (var key in obj.faces) {
      var face = obj.faces[key];
      if (face.texture !== null) {
        template.uv[key] = new oneLiner({
          uv: [face.uv[0], face.uv[1]],
          uv_size: squareSize(face.uv),
        });
        // TODO: No clue what's that
        // if (face.material_name) {
        //   template.uv[key].material_instance = face.material_name;
        // }
        if (key == "up" || key == "down") {
          template.uv[key].uv[0] += template.uv[key].uv_size[0];
          template.uv[key].uv[1] += template.uv[key].uv_size[1];
          template.uv[key].uv_size[0] *= -1;
          template.uv[key].uv_size[1] *= -1;
        }
      }
    }
  }
  return template;
}

function cubeSize(scope) {
  function getA(axis) {
    return scope.to[axis] - scope.from[axis];
  }
  return [getA(0), getA(1), getA(2)];
}

function squareSize(scope) {
  return [scope[2] - scope[0], scope[3] - scope[1]];
}

function allEqual0(a) {
  return a[0] === 0 && a[1] === 0 && a[2] === 0;
}

class oneLiner {
  constructor(data) {
    if (data !== undefined) {
      for (var key in data) {
        if (data.hasOwnProperty(key)) {
          this[key] = data[key];
        }
      }
    }
  }
}

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

// function calculateVisibleBox() {
//   var visible_box = new THREE.Box3();
//   Canvas.withoutGizmos(() => {
//     Cube.all.forEach((cube) => {
//       if (cube.export && cube.mesh) {
//         visible_box.expandByObject(cube.mesh);
//       }
//     });
//   });

//   var offset = new THREE.Vector3(8, 8, 8);
//   visible_box.max.add(offset);
//   visible_box.min.add(offset);

//   // Width
//   var radius = Math.max(
//     visible_box.max.x,
//     visible_box.max.z,
//     -visible_box.min.x,
//     -visible_box.min.z
//   );
//   if (Math.abs(radius) === Infinity) {
//     radius = 0;
//   }
//   let width = Math.ceil((radius * 2) / 16);
//   width = Math.max(width, Project.visible_box[0]);
//   Project.visible_box[0] = width;

//   //Height
//   let y_min = Math.floor(visible_box.min.y / 16);
//   let y_max = Math.ceil(visible_box.max.y / 16);
//   if (y_min === Infinity) y_min = 0;
//   if (y_max === Infinity) y_max = 0;
//   y_min = Math.min(y_min, Project.visible_box[2] - Project.visible_box[1] / 2);
//   y_max = Math.max(y_max, Project.visible_box[2] + Project.visible_box[1] / 2);

//   Project.visible_box.replace([width, y_max - y_min, (y_max + y_min) / 2]);

//   return Project.visible_box;
// }
