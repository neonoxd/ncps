# ~~N~~Curses Proton environment Setter
Provides a simple curses based user interface for setting up your proton environment and related variables
by selecting a "compatdata" and a "proton" folder aimed to use in tandem with automated protontricks scripts

![image](https://user-images.githubusercontent.com/2606522/227482034-08bb6c66-f3aa-44ea-ab64-98585a56beb9.png)
![image](https://user-images.githubusercontent.com/2606522/227482155-bee79bc2-562e-4587-81d4-e76eadb0ecc6.png)


After the selection has been made the script sets the following variables for the passed command
- PROTON 
  - Path to root folder of Proton
- WINEPREFIX
  - pfx folder of the selected wineprefix/compatdata folder
- PATHEXTRA
  - path to the bin folder of Proton
- WINESERVER
  - path to the wineserver binary
- WINELOADER
  - path to the wineloader binary
- WINEDLLPATH
  - path entry string containing lib/wine:lib64/wine
- APPID
  - APPID of selected wineprefix/compatdata

## Installation
Simply run `./install.sh` then you can use the `ncps` command

## Usage
`ncps /path/to/script params` or `ncps -c '/path/to/script params $envvar_as_param'`

### Set Env & Execute script with params
```sh
$ ncps ./cool_protontricks_script.sh -coolparams
... user interaction
$ hey i'm cool_protontricks_script.sh and received -coolparams and some PROTON env vars
```
### Set Env & Execute script with params in shell mode
#### Allowing for expanding enviroment variables after they have been set by the tool
```sh
$ ncps -c './cool_protontricks_script_that_needs_appid.sh -coolparams $APPID'
... user interaction, selects app having 123realAppid
$ hey i'm cool_proton_script_that_needs_appid.sh and received -coolparams and 123realAppid as parameters
```
or
```sh
$ ncps -c 'echo hello $PROTON'
... user interaction
$ hello /home/deck/Steam/compatibilitytools.d/ProtonGE5
```

## Known Issues & Planned updates
- Prefix selector shows UNKNOWN for apps that are no longer installed, might use steamapi with caching to get app name
- PgUP/PgDn & Mouse support is missing
- Option to reuse last selected environment

## Note
This script is primarily created for the Steam Deck

The curses menu can be navigated using the DPAD making it significantly easier to execute protontricks scripts

However, it _should_ _Just Work_ on a standard computer running linux
