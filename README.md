# Reflow Oven

Based on EZ Make Oven by Adafruit.

* Sparkfun MCP9600 with QWIIC connectors
* Hamilton Beach Countertop Toaster Oven & Pizza Maker 31401
* Adafruit Metro M4 feat. Microchip ATSAMD51
* Adafruit "Music Maker" MP3 Shield for Arduino w/3W Stereo Amp
* Speaker - 40mm Diameter - 4 Ohm 3 Watt
* 2.8" TFT Touch Shield for Arduino w/Capacitive Touch
* SSR-25DA DC->AC. https://www.amazon.com/gp/product/B08GPJ1V2J 

The toaster oven should disassembled and insulated. This is a good guide:
https://www.whizoo.com/reflowoven
Don't skimp on the reflective tape on the door! Be careful about wiring as 110V is involved.

Pry the knobs off the front panel. I suggest using a regular screwdriver from the back and twisting
to pry it up. Once off, unscrew all the controls so you're left with the bent sheetmetal. Print
the front panel in a higher temp plastic (though it really wont have to handle much heat). I printed
in Nylon. ABS should work too. Using a dremal + grinder (or something similar) carefully cutout a rectangle
to fit the front panel. Insert threaded inserts into the screw holes in the front panel. These work great:
https://www.amazon.com/gp/product/B07LBRR2ZB/
And screw it into place in the sheet metal front panel. The rest is just wiring, testing, and re-assembling.

Future work:
* Consider swapping to Arduino code over Circuit Python. Circuit Python is very slow, especially for playing
sounds.
