# Color Swap King
Color Swap King analyzes Bambu Labs (and compatible) GCode.3MF files to produce a customizable and printable checklist of color swaps for the user. 3D printers don't actually tell the user which filament to swap to when using multiple manual swapped filaments, and many of them don't show the current layer number when the "insert filament" message is displayed.  This causes a significant challenge for users who aren't afraid to use manual filament swaps, and Color Swap King makes it so much easier.

## Main Features
- Portable EXE file, no installation required! Totally self-contained in one file.
- Easy to use GUI.
- Drag and drop file loading.
- Full Bambu Labs GCode.3MF support.
- Allows the user to specify which colors require manual swaps and matches them to the GCode's swaps.
- Automatically generates a filament color legend with color previews from the GCode.
- Generates a full list of manual filament swaps based on the user's manually swapped filaments.
- Exports a printable HTML checklist and allows the user to decide how many columns to use and what information to include.

## How It Does It
- Analyzes Bambu Labs compatible 3MF Gcode and parses filament swap and print information.
- Reads Bambu filament metadata and color information from the GCode. 
- Normalizes Bambu's filament numbering in a user friendly way.
- Checks multiple ways, finds, and finds all manual (and automatic if you like) color swaps regardless of incomplete GCode comments.
- Tracks the swap sequence number and layer height for each filament swap.
- Preserves raw GCode line numbers for all of you Power Users ;).

## Future Development
- Generic G-code parser testing / tuning.
- Printable PDF checklist export option.
- Other format support and testing.
- Porting or rebuilding for other operating systems.

