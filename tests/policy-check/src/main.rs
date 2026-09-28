//! Read-only validation with the exact AppPolicy revision pinned by target Rinx.
//! This is a developer check, not an app backend or a Rinx UI acceptance test.
use octosense_app_policy::{admit_digest, digest_dir, policy, AppManifest, HostLimits, RefuseAllSignatures};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let root = std::path::PathBuf::from(std::env::args_os().nth(1).ok_or("bundle path required")?);
    let manifest = AppManifest::parse(&std::fs::read_to_string(root.join("manifest.json"))?)?;
    if manifest.agent.is_some() { return Err("Rinx does not accept bundle agent profiles".into()); }
    admit_digest(&manifest, &digest_dir(&root)?, &RefuseAllSignatures)?;
    let grants = policy::resolve(&manifest, &HostLimits { require_signature: false, ..Default::default() })?;
    let script = octosense_app_policy::script_source(&root, "http://127.0.0.1:1234/").ok_or("missing main.splash")??;
    if script.is_empty() { return Err("empty main.splash".into()); }
    println!("PASS target Rinx AppPolicy e8601b80: {} {} · {} script bytes · {:?}", manifest.id, manifest.version, script.len(), grants.capabilities);
    Ok(())
}
