# Windows practice app: signed release candidate only

**What the attorney should eventually see:** one MyTravelingLawyer-Practice.exe, with Create Practice Case and Open Practice Case. No command prompts, ZIP hunting, separate Python install or real case data.

**Current status:** source-only packaging design. No executable built or signed. This branch does not change draft PR #110.

**Why not signed yet?** Microsoft Smart App Control requires a recognized trusted publisher certificate; a free self-signed certificate will not work. An approved CA-backed signing certificate or Azure Artifact Signing identity must be provisioned by the owner, or an approved Microsoft Store MSIX route chosen. Cost and account ownership require separate approval.

**Only after owner approves signing identity:** use an authorized Windows build system with vetted Python 3.11, PyInstaller and Windows SDK SignTool. Build this branch and run `tools/build_signed_windows.ps1` with the approved certificate's thumbprint. It must sign or trust all EXE/DLL/PYD files and verify every certificate chain. Never upload unsigned output for attorney testing. Never modify Smart App Control policy.

**Still required after signing:** independent Smart App Control ON test, startup/login, no-overwrite/restart/privacy/second-review tests, an independent human attorney usability verdict and an independent qualified security verdict. Original 42-file published gate remains 32/42, ten restricted originals unpublished, no custody approval, no production release.

**Protected source:** PR #110 SHA c0b94e0eae172f3ea1deeb34800797b13edbcc8e, Actions 43269276424, Windows 58/58 native Tk, 12/12 login/restart, 9/9 backup/restore.
