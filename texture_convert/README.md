# Texture Convert

## Psd Convert

`.psd` files are image files from the popular image editor [Photoshop](https://www.adobe.com/products/photoshop.html).

This filter will check the project for any `.psd` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.psd` files directly inside of your addon, without converting them manually whenever you make a change.

## Kra Convert

`.kra` files are image files from the popular image editor [Krita](https://krita.org/en/).

This filter will check the project for any `.kra` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.kra` files directly inside of your addon, without editing them manually whenever you make a change.

## Gimp Convert
`.xcf` files are image files from the open source image editor [Gimp](https://www.gimp.org/).

This filter will check the project for any `.xcf` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.xcf` files directly inside of your addon, without converting them manually whenever you make a change.

## Paint.net Convert
`.pdn` files are image files from the free image editor [Paint.net](https://https://www.getpaint.net).

This filter will check the project for any `.pdn` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.pdn` files directly inside of your addon, without converting them manually whenever you make a change.

##  GIF Convert
`.gif` files are converted into vertical sprite sheets (`.png` files) with the same name and file location.

## Using the Filter

```json
{
    "filter": "texture_convert"
}
```

## Changelog

### 1.2.0
Added support for `.gif` files.

### 1.1.1

- Fixed an error, when file was without an extension

### 1.1.0

- Add support for paint.net's `.pdt` files
- Clean up the code

### 1.0.0

The first release of Texture Convert.