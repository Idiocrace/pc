# PC Sim Syntax Extension

This extension adds syntax highlighting for `.sim` files used by the PC simulator format.

## Features

- Language id: `pcsim`
- File extension mapping: `.sim`
- Line comments: `#`
- TextMate scopes for:
  - `@meta`
  - Component names (`relay(...)`, `wire(...)`, etc.)
  - Attribute keys (`id=`, `vcc=`, etc.)
  - Numbers and booleans
  - Punctuation and assignment operator

## Run In VS Code

1. Open `vscode/pc-sim-syntax` in VS Code.
2. Press `F5` to launch an Extension Development Host.
3. In the new window, open any `.sim` file.

## Package As VSIX

1. Install packager: `npm i -g @vscode/vsce`
2. From `vscode/pc-sim-syntax`, run: `vsce package`
3. Install generated `.vsix` from VS Code: `Extensions: Install from VSIX...`
