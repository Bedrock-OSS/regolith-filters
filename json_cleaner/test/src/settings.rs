//! Filter settings, passed by Regolith as a single JSON argument.

use serde::Deserialize;

/// Public settings of the filter. Both default to `false`.
///
/// Unknown properties are ignored (the previous implementation merged the
/// argument with `Object.assign` and never looked at other keys). A known
/// property with a wrong type is an error.
#[derive(Clone, Copy, Debug, Default, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", default)]
pub struct Settings {
    pub strip_schemas: bool,
    pub minify: bool,
}

impl Settings {
    /// Parses the settings argument. `None` or an empty string yields the
    /// defaults. The argument must be a JSON object.
    pub fn parse(arg: Option<&str>) -> Result<Settings, String> {
        match arg {
            None => Ok(Settings::default()),
            Some(s) if s.trim().is_empty() => Ok(Settings::default()),
            Some(s) => {
                let value: serde_json::Value = serde_json::from_str(s)
                    .map_err(|e| format!("invalid settings argument {s:?}: {e}"))?;
                if !value.is_object() {
                    return Err(format!(
                        "invalid settings argument {s:?}: expected a JSON object"
                    ));
                }
                serde_json::from_value::<Settings>(value)
                    .map_err(|e| format!("invalid settings argument {s:?}: {e}"))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults() {
        assert_eq!(Settings::parse(None).unwrap(), Settings::default());
        assert_eq!(Settings::parse(Some("")).unwrap(), Settings::default());
        assert_eq!(Settings::parse(Some("{}")).unwrap(), Settings::default());
        assert!(!Settings::default().minify);
        assert!(!Settings::default().strip_schemas);
    }

    #[test]
    fn known_settings() {
        let s = Settings::parse(Some(r#"{"stripSchemas": true, "minify": true}"#)).unwrap();
        assert!(s.strip_schemas && s.minify);
        let s = Settings::parse(Some(r#"{"minify": true}"#)).unwrap();
        assert!(!s.strip_schemas && s.minify);
    }

    #[test]
    fn unknown_settings_are_ignored() {
        let s = Settings::parse(Some(r#"{"minify": true, "somethingElse": 5}"#)).unwrap();
        assert!(s.minify);
    }

    #[test]
    fn errors() {
        assert!(Settings::parse(Some("{")).is_err());
        assert!(Settings::parse(Some("null")).is_err());
        assert!(Settings::parse(Some("[]")).is_err());
        assert!(Settings::parse(Some(r#"{"minify": "true"}"#)).is_err());
        assert!(Settings::parse(Some(r#"{"stripSchemas": 1}"#)).is_err());
    }
}
