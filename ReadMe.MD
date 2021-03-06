# BeoGateway: Indigo Server Plugin for Bang and Olufsen AV Systems

![](Resources/Bang-Olufsen-Logo.png)

*Please note this plugin is not endorsed or affiliated with Bang & Olufsen in any way*

## Introduction
	
Plugin for the [Indigo Domotics](https://www.indigodomo.com) Home Automation software allowing integration and control of Bang and Olufsen AV systems. 
The plugin provides the following functionality:

- Defines an Indigo AV Renderer device type with state monitoring of 
  - Current Source ID and Source Name 
  - PlayState 
  - Current Channel/Track Number and Name
  - Volume
- Light and appliance control via Beo4/BeoRemote One LIGHT and CONTOL commands
- Native control of [Apple Music](https://github.com/LukeSpad/BeoGateway/edit/Indigo-Server-Plugin/ReadMe.MD#apple-music-control) via user defined audio source (*N.MUSIC by default*), using Beo4/BeoRemote One to control transport 
- One touch activation of audio experiences via Indigo UI, any Indigo trigger, or Apple Home app. [^1]  
  - If all sources are in standby, a single press starts a pre-defined default audio experience (*RADIO by default*)
  - If sources are already playing, a single press joins the current audio experience
- Send [Home Integration Protocol](https://github.com/LukeSpad/BeoGateway#home-integration-protocol-commands) commands to the gateway (BLGW only)
- State change reporting in the [Apple Notification Center](https://github.com/LukeSpad/BeoGateway/edit/Indigo-Server-Plugin/ReadMe.MD#state-reporting-in-apple-notification-centre)
- [Protocol Monitoring](https://github.com/LukeSpad/BeoGateway/edit/Indigo-Server-Plugin/ReadMe.MD#protocol-monitoring) and reporting of traffic on the Bang and Olufsen MasterLink network, including:
  - MasterLink packet information, 
  - MLGW protocol data, and 
  - Home Automation Protocol data
  
[1]: Via the [HomeKit Bridge](https://www.indigodomo.com/pluginstore/172/) Plugin 

## Requirements
	

The code requires a MasterLink or BeoLink Gateway to run - it is untested with the BeoLiving Intelligence

Compatible with legacy DataLink (via 1611 converter), MasterLink, and modern NetworkLink products, including the BeoLink Converter ML/NL.

## Basic Setup and Use
	
1. Install the plugin from the Indigo Plugin Store.
2. Configure the plugin providing the following information for your gateway: 
   1. IP address, 
   2. port, 
   3. login and password
3. Select the default audio source for devices. You can toggle Apple Music control On/Off and assign it to a particular source
4. The plugin will download the configuration from the gateway and create AV renderer devices accordingly
5. Devices can only access sources defined in their config on the gateway and will recognise at least the channel/tracks included in their favourites lists. Some sources (e.g. NetworkLink sources) may recognise additional channels and track data.
6. Devices can be switched On/Off and toggled via the indigo UI

## Advanced Functions
	
### Plugin Events/Triggers
	
The plugin can respond to various events on the B&O network including:
- All Standby Events
- Light Commands
- Control Commands
- Beo4/BeoRemote One Commands to a Specific Source
- Virtual Button presses 

These events can be found under the 'BeoGateway Plugin Event' list in Indigo's Create New Trigger dialogue 

### Plugin Actions
	
Indigo Events can trigger a number of actions on the B&O Network including:
	
#### BeoGateway Plugin Actions:
	
- Request BLGW Home Integration Protocol State Updates for all devices
- Send a BLGW Home Integration Protocol Command (*only on BLGW - see below*)
- Send Free Text Integration Protocol Command (*for advanced users - see below*)
- Send Virtual Button
- Post a Message to the Notification Centre (*see below*)
- Send All Standby Command

#### BeoGateway Device Actions:
	
- Send Beo4 Source Selection Command
- Send Beo4 Key
- Send BeoRemote One Source Selection Command
- Send BeoRemote One Key
- Request Device State Update

### Protocol Monitoring
	
Network traffic monitoring to the Indigo log be toggled in the plugin config menu:
- [x] Verbose Mode

A typical message is formatted as follows:
```
BeoGateway Plugin               
    ----------------------------------------------------------------------------
    BLGW Home Integration Protocol: <--DATA-RECEIVED!-<< on 05/02/22 at 17:13:32
    ============================================================================
    Header: ['s Downstairs', 'Dining Room', 'AV renderer', 'BeoMaster 7000']
    Payload: ['nowPlaying=', 'nowPlayingDetails=type: Legacy; track number: 2',
	 'online=Yes', 'sourceName=RADIO', 'sourceUniqueId=RADIO:1790.1179011.2
	6002135@products.bang-olufsen.com', 'state=Play', 'volume=26']
    ----------------------------------------------------------------------------
    Zone: DOWNSTAIRS 
    Room: DINING ROOM 
    Type: AV RENDERER 
    Device: BeoMaster 7000 
    State_Update: 
        nowPlaying: BBC Radio 2 
        nowPlayingDetails: 
            type: Legacy 
            channel_track: 2
         
        online: Yes 
        sourceName: RADIO 
        source: RADIO 
        sourceUniqueId: RADIO:1790.1179011.26002135@products.bang-olufsen.com 
        state: Play 
        volume: 26
```

### Apple Music Control
	
Apple Music control can be toggled in the plugin config menu:
- [x] Control Apple Music

It will also report the current track information to the indigo log if 'post notifications' is toggled:
- [x] post notifications

A typical track readout looks like this:
```
BeoGateway Plugin               
    ----------------------------------------------------------------------------
    iTUNES CURRENT TRACK INFO:
    ============================================================================
    Now playing: 'Eh, Petite Fille'
                  by Clifton Chenier
                  from the album 'Bayou Blues'
    ----------------------------------------------------------------------------
    ACTIVE AUDIO RENDERERS: Hallway Beolink Active
```

If the plugin is configured to map a source to Apple Music, selection of that source on your remote will initiate playback immediately, shuffling from the entire library. 
If other AV renderers join the music experience playback is unaffected. Apple Music will stop playing when all active audio renderers go into a Standby state.

The controls are mapped as follows:

| Beo4 Key | BeoRemote One Key | Apple Music Action |
| ----------- | ----------- | ----------- |
| Go | Play | Play
| Stop | Pause | Pause
| Wind | Wind | Scan Forwards 15 Seconds
| Rewind | Rewind | Scan Backwards 15 Seconds
| Step Up | P+ | Next Track
| Step Down | P- | Previous Track
| Shift-1/Random | Random | Toggle Shuffle
| - | Info | Produce Notification of Current Track Info and Print to Indigo Log
| - | Guide | Print this table to Indigo Log
| Green | Green | Shuffle Playlist 'Recently Played'
| Yellow | Yellow | Play Digital Radio Stations from Playlist 'Radio'
| Red | Red | More of the Same
| Blue | Blue | Play the Album that the Current Track Resides On 

### State Reporting in Apple Notification Centre
	
State reports in the notification centre can be toggled in the config menu
- [x] Post Notifications

![](Resources/Notification.png)

It is also possible to trigger notifications via any Indigo event using the action:
"BeoGateway Plugin Actions/Post Message in Notification Centre"

### Home Integration Protocol Commands
	
The BeoLink Gateway (BLGW) provides a Home Integration Protocol for external automation services to communicate with devices on the B&O Network.

A copy of the documentation for the protocol is included in the plugin's Resources/Documentation folder, and the overview below is lifted from that document.
>With the introduction of BLGW, there is a standard way of identifying resources and specifying
activity and state in the connected systems. Such activity can be represented unambiguously in
the form of a text string.

>Home Integration Protocol allows external applications to directly interact with BLGW. This is done
by means of a minimalist line-based protocol that directly transports the text representation of all
activity.  
 
>A resource is uniquely identified by the combination of zone, room, type and name, and is represented
uniquely in string form as a path with the form zone/room/type/name. 
>
>For example:
 
```
Guest house/Kitchen/AV_RENDERER/BeoVision/
```
>An event or command is represented by a resource path followed by an action (event or command),
optionally followed by attributes and values.
> 
>Example of a simple command, and a command with 2 attributes:
```
Guest house/Kitchen/BUTTON/Lights ON/PRESS
```
```
Guest house/Kitchen/AV_RENDERER/BeoVision/Beo4 command?Command=TV&Destination selector=Video_source
```
>Example state change event, with 1 attribute.
```
Guest house/Kitchen/BUTTON/Lights ON/STATE_UPDATE?STATE=1
```
>Example generic event matching all state updates (see documentation for generic programming):
```
*/*/*/*/STATE_UPDATE
```
The following commands are supported on HIP:

| Command | Arguments | Description |
| ----------- | ----------- | ----------- |
| c | Generic ID | Command, from client to server.
| f | Generic resource | State filter request, client to server.
| e | Code, message | Error code, server to client.
| q | Generic resource | State query, client to server.
| s | Specific ID | State update, server to client.
| r | Specific ID | State response, client to server.

>All commands from client to server take a single argument, which is an identifier for resources,
commands or events.

>A complete message consists of:
>1. The command (1 character)
>2. Space (ASCII 0x20)
>3. The argument, which is an encoded string
>4. Line termination, consisting of CR+LF (the server will also accept a single CR)

>For example, to press all buttons in the installation, the client sends (do not try this at home):
```
c */*/BUTTON/*/PRESS" + CR + LF
```
## Credits
	
The code draws heavily on the existing [MLGW](https://github.com/giachello/mlgw) project by user Giachello,
but is recoded for Python 2.7. His work underpins the decoding of raw MasterLink packets for the ML Command Line Protocol.
