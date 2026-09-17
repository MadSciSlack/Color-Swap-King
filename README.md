# Color Swap King
Color Swap King analyzes GCode files (Bambu compatible and generic) to produce a customizable and printable checklist of color swaps for the user. 3D printers don't actually tell the user which filament to swap to when using multiple manual swapped filaments, and many of them don't show the current layer number when the "insert filament" message is displayed.  This causes a significant challenge for users who aren't afraid to use manual filament swaps, and Color Swap King makes it so much easier.

## What It Does
- Portable EXE file, no installation required! Totally self-contained in one file.
- Easy to use GUI, drag and drop file loading.
- Can easily handle MASSIVE GCode files.
- Full Bambu Labs GCode.3MF support.
- Full support for GCode files made with most slicers.
- Allows the user to specify which colors require manual swaps and matches them to the GCode's swaps.
- Allows the user to also include automatic filament swaps.
- Automatically generates a filament color legend with color previews from the GCode.
- Generates a full list of manual filament swaps based on the user's manually swapped filaments.
- Exports a printable HTML checklist and allows the user to decide how many columns to use and what information to include.
- Exports to a printable PDF file with the same customization options.
- Specify a range by layer numbers, for example, manual swaps between layer 50 and 100.

## How It Does It
- Analyzes the GCode file to identify the type.
- Directs Bambu Labs compatible 3MF Gcode to a dedicated module and parses filament swap and print information.
- Directs other GCode to a generalized module and parses filament swap and print information.
- Reads filament metadata and color information from the GCode. 
- Normalizes filament numbering in a user friendly way.
- Checks multiple ways and finds all manual (and automatic if you like) color swaps, even when GCode comments are incomplete.
- Tracks the swap sequence number and layer height for each filament swap.
- A little of HTML for the export, a little QT / PySide6 for the UI, and a whole lot of Python behind the scenes.

## How to Use It
Download the app EXE here: https://github.com/MadSciSlack/Color-Swap-King/releases/download/V0.60-B0013/ColorSwapKing.exe. That file is located here in this repository.
Download the app EXE here: [https://github.com/MadSciSlack/Color-Swap-King/releases/download/V0.60-B0013/color_swap_king.exe](https://github.com/MadSciSlack/Color-Swap-King/releases/download/V0.60-B0013/color_swap_king.exe). That file is located here in this repository through Github's Large File Storage (LFS).
Put the file wherever you want to keep it and launch it from.  You can also create a shortcut to it and tuck it away if you prefer that.  You don't need to setup or install it, it's ready to go!
Open the app EXE, drop in your GCode.3MF file, check the boxes by your manual filaments, and export. You can choose the layout options, which extra information to include, and whether to include automatic filament swaps in the checklist.


## Future Development
- Other format support and testing.
- Porting or rebuilding for other operating systems.
If you are able to support my development, you are able to tip ko-fi.com/madscislack.
Thank you to anyone who chooses to help, it means a lot.
