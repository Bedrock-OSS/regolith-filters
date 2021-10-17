# Kra Convert

`.kra` files are image files from the popular image editor [Krita](https://krita.org/en/).

This filter will check the project for any `.kra` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.kra` files directly inside of your addon, without editing them manually whenever you make a change.

## Using the 

```json
{
    "filter": "kra_convert"
}
```