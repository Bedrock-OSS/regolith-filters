const PSD = require("PSD");
const glob = require("glob");
const fs = require("fs");

glob("RP/textures/**/*.psd", null, function (er, files) {
  files.forEach(function (file) {
    PSD.open(file).then(function (psd) {
      let png = file.substr(0, file.length - 3) + "png";
      console.log("Converting " + file + " into " + png);
      psd.image.saveAsPng(png);
      fs.unlinkSync(file);
    });
  });
});
