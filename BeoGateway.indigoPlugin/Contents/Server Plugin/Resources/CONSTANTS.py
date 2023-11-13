from collections import OrderedDict


# Constants for B&O telegram protocols
# ########################################################################################
# Config data (set on initialisation)
rooms = []
available_sources = []

standby_state = [
    {'key': 'onOffState', 'value': False},
    {'key': 'playState', 'value': 'Standby'},
    {'key': 'source', 'value': 'Standby'},
    {'key': 'nowPlaying', 'value': 'Unknown'},
    {'key': 'channelTrack', 'value': 0},
    {'key': 'mute', 'value': True},
    {'key': 'volume', 'value': 0},
]

gw_all_stb = [
    {'key': 'AudioRenderers', 'value': ''},
    {'key': 'VideoRenderers', 'value': ''},
    {'key': 'nAudioRenderers', 'value': 0},
    {'key': 'nVideoRenderers', 'value': 0},
    {'key': 'currentAudioSource', 'value': 'Unknown'},
    {'key': 'currentAudioSourceName', 'value': 'Unknown'},
    {'key': 'nowPlaying', 'value': 'Unknown'},
]

# ########################################################################################
# Source Types

source_type_dict = dict(
    [
        ("Video Sources", ("TV", "V.AUX/DTV2", "MEDIA", "V.TAPE/V.MEM/DVD2", "DVD", "DVD2", "CAMERA",
                           "SAT/DTV", "PC", "WEB", "DOORCAM", "PHOTO", "USB2", "WEBMEDIA", "AV.IN",
                           "HOMEMEDIA", "DVB_RADIO", "DNLA", "RECORDINGS", "CAMERA", "USB", "DNLA-DMR", "YOUTUBE",
                           "HOME.APP", "HDMI_1", "HDMI_2", "HDMI_3", "HDMI_4", "HDMI_5", "HDMI_6",
                           "HDMI_7", "HDMI_8", "MATRIX_1", "MATRIX_2", "MATRIX_3", "MATRIX_4", "MATRIX_5",
                           "MATRIX_6", "MATRIX_7", "MATRIX_8", "MATRIX_9", "MATRIX_10", "MATRIX_11",
                           "MATRIX_12", "MATRIX_13", "MATRIX_14", "MATRIX_15", "MATRIX_16", "PERSONAL_1",
                           "PERSONAL_2", "PERSONAL_3", "PERSONAL_4", "PERSONAL_5", "PERSONAL_6", "PERSONAL_7",
                           "PERSONAL_8")),
        ("Audio Sources", ("RADIO", "A.AUX", "A.TAPE/A.MEM", "CD", "PHONO/N.RADIO", "A.TAPE2/N.MUSIC",
                           "SERVER", "SPOTIFY", "CD2/JOIN", "TUNEIN", "DVB_RADIO", "LINE.IN", "BLUETOOTH",
                           "MUSIC", "AIRPLAY", "SPOTIFY", "DEEZER", "QPLAY"))
    ]
)

# ########################################################################################
# Beo4 Commands
beo4_srcdict = OrderedDict(
    [
        # Source selection:
        (0x0C, "Standby"),
        (0x47, "Sleep"),
        (0x80, "TV"),
        (0x81, "Radio"),
        (0x82, "V.Aux/DTV2"),
        (0x83, "A.Aux"),
        (0x84, "Media"),
        (0x85, "V.Tape/V.Mem"),
        (0x86, "DVD"),
        (0x87, "Camera"),
        (0x88, "Text"),
        (0x8A, "Sat/DTV"),
        (0x8B, "PC"),
        (0x8C, "Web"),
        (0x8D, "Doorcam"),
        (0x8E, "Photo"),
        (0x90, "USB2"),
        (0x91, "A.Tape/A.Mem"),
        (0x92, "CD"),
        (0x93, "Phono/N.Radio"),
        (0x94, "A.Tape2/N.Music"),
        (0x95, "Server"),
        (0x96, "Spotify"),
        (0x97, "CD2/Join"),
        (0xBF, "AV"),
    ]
)

beo4_commanddict = OrderedDict(
    [
        # Source selection:
        (0x0C, "Standby"),
        (0x47, "Sleep"),
        (0x80, "TV"),
        (0x81, "Radio"),
        (0x82, "V.Aux/DTV2"),
        (0x83, "A.Aux"),
        (0x84, "Media"),
        (0x85, "V.Tape/V.Mem"),
        (0x86, "DVD"),
        (0x87, "Camera"),
        (0x88, "Text"),
        (0x8A, "Sat/DTV"),
        (0x8B, "PC"),
        (0x8C, "Web"),
        (0x8D, "Doorcam"),
        (0x8E, "Photo"),
        (0x90, "USB2"),
        (0x91, "A.Tape/A.Mem"),
        (0x92, "CD"),
        (0x93, "Phono/N.Radio"),
        (0x94, "A.Tape2/N.Music"),
        (0x95, "Server"),
        (0x96, "Spotify"),
        (0x97, "CD2/Join"),
        (0xBF, "AV"),
        (0xFA, "P-IN-P"),
        # Digits:
        (0x00, "Digit-0"),
        (0x01, "Digit-1"),
        (0x02, "Digit-2"),
        (0x03, "Digit-3"),
        (0x04, "Digit-4"),
        (0x05, "Digit-5"),
        (0x06, "Digit-6"),
        (0x07, "Digit-7"),
        (0x08, "Digit-8"),
        (0x09, "Digit-9"),
        # Source control:
        (0x1E, "Step Up"),
        (0x1F, "Step Down"),
        (0x32, "Rewind"),
        (0x33, "Return"),
        (0x34, "Wind"),
        (0x35, "Go/Play"),
        (0x36, "Stop"),
        (0xD4, "Yellow"),
        (0xD5, "Green"),
        (0xD8, "Blue"),
        (0xD9, "Red"),
        # Sound and picture control
        (0x0D, "Mute"),
        (0x1C, "P.Mute"),
        (0x2A, "Format"),
        (0x44, "Sound/Speaker"),
        (0x5C, "Menu"),
        (0x60, "Volume Up"),
        (0x64, "Volume Down"),
        (0xDA, "Cinema_On"),
        (0xDB, "Cinema_Off"),
        # Other controls:
        (0x7C, "Status"),   # ??? 0x5D ???
        (0xF7, "Stand"),
        (0x0A, "Clear"),
        (0x0B, "Store"),
        (0x0E, "Reset"),
        (0x14, "Back"),
        (0x15, "MOTS"),
        (0x20, "Goto"),
        (0x28, "Show Clock"),
        (0x2D, "Eject"),
        (0x37, "Record"),
        (0x3F, "Select"),
        (0x46, "Sound"),
        (0x7F, "Exit"),
        (0xC0, "Shift-0/Edit"),
        (0xC1, "Shift-1/Random"),
        (0xC2, "Shift-2"),
        (0xC3, "Shift-3/Repeat"),
        (0xC4, "Shift-4/Select"),
        (0xC5, "Shift-5"),
        (0xC6, "Shift-6"),
        (0xC7, "Shift-7"),
        (0xC8, "Shift-8"),
        (0xC9, "Shift-9"),
        # Continue functionality:
        (0x70, "Rewind Repeat"),
        (0x71, "Wind Repeat"),
        (0x72, "Step_UP Repeat"),
        (0x73, "Step_DW Repeat"),
        (0x75, "Go Repeat"),
        (0x76, "Green Repeat"),
        (0x77, "Yellow Repeat"),
        (0x78, "Blue Repeat"),
        (0x79, "Red Repeat"),
        (0x7E, "Key Release"),
        # Functions:
        (0x40, "Guide"),
        (0x43, "Info"),
        (0xE3, "Home Control"),
        (0x0F, "Function_1"),
        (0x10, "Function_2"),
        (0x11, "Function_3"),
        (0x12, "Function_4"),
        (0x19, "Function_5"),
        (0x1A, "Function_6"),
        (0x21, "Function_7"),
        (0x22, "Function_8"),
        (0x23, "Function_9"),
        (0x24, "Function_10"),
        (0x25, "Function_11"),
        (0x26, "Function_12"),
        (0x27, "Function_13"),
        (0x39, "Function_14"),
        (0x3A, "Function_15"),
        (0x3B, "Function_16"),
        (0x3C, "Function_17"),
        (0x3D, "Function_18"),
        (0x3E, "Function_19"),
        (0x4B, "Function_20"),
        (0x4C, "Function_21"),
        (0x50, "Function_22"),
        (0x51, "Function_23"),
        (0x7D, "Function_24"),
        (0xA5, "Function_25"),
        (0xA6, "Function_26"),
        (0xA9, "Function_27"),
        (0xAA, "Function_28"),
        (0xDD, "Function_29"),
        (0xDE, "Function_30"),
        (0xE0, "Function_31"),
        (0xE1, "Function_32"),
        (0xE2, "Function_33"),
        (0xE6, "Function_34"),
        (0xE7, "Function_35"),
        (0xF2, "Function_36"),
        (0xF3, "Function_37"),
        (0xF4, "Function_38"),
        (0xF5, "Function_39"),
        (0xF6, "Function_40"),
        # Cursor functions:
        (0x13, "Select"),
        (0xCA, "Cursor_Up"),
        (0xCB, "Cursor_Down"),
        (0xCC, "Cursor_Left"),
        (0xCD, "Cursor_Right"),
        # Light/Control commands
        (0x9B, "Light"),
        (0x9C, "Command"),
        (0x58, "Light Timeout"),
        #  Dummy for 'Listen for all commands'
        (0xFF, "<all>"),
    ]
)
BEO4_CMDS = {v.upper(): k for k, v in beo4_commanddict.items()}

# BeoRemote One Commands
beoremoteone_commanddict = OrderedDict(
    [
        # Source, (Cmd, Unit)
        ("Standby", (0x0C, 0)),
        ("TV", (0x80, 0)),
        ("RADIO", (0x81, 0)),
        ("TUNEIN", (0x81, 1)),
        ("DVB_RADIO", (0x81, 2)),
        ("AV.IN", (0x82, 0)),
        ("LINE.IN", (0x83, 0)),
        ("A.AUX", (0x83, 1)),
        ("BLUETOOTH", (0x83, 2)),
        ("HOMEMEDIA", (0x84, 0)),
        ("DNLA", (0x84, 1)),
        ("RECORDINGS", (0x85, 0)),
        ("CAMERA", (0x87, 0)),
        ("FUTURE.USE", (0x89, 0)),
        ("USB", (0x90, 0)),
        ("A.MEM", (0x91, 0)),
        ("CD", (0x92, 0)),
        ("N.RADIO", (0x93, 0)),
        ("A.TAPE2/N.MUSIC", (0x94, 0)),
        ("MUSIC", (0x94, 0)),
        ("DNLA-DMR", (0x94, 1)),
        ("AIRPLAY", (0x94, 2)),
        ("SPOTIFY", (0x96, 0)),
        ("DEEZER", (0x96, 1)),
        ("QPLAY", (0x96, 2)),
        ("JOIN", (0x97, 0)),
        ("WEBMEDIA", (0x8C, 0)),
        ("YOUTUBE", (0x8C, 1)),
        ("HOME.APP", (0x8C, 2)),
        ("HDMI_1", (0xCE, 0)),
        ("HDMI_2", (0xCE, 1)),
        ("HDMI_3", (0xCE, 2)),
        ("HDMI_4", (0xCE, 3)),
        ("HDMI_5", (0xCE, 4)),
        ("HDMI_6", (0xCE, 5)),
        ("HDMI_7", (0xCE, 6)),
        ("HDMI_8", (0xCE, 7)),
        ("MATRIX_1", (0xCF, 0)),
        ("MATRIX_2", (0xCF, 1)),
        ("MATRIX_3", (0xCF, 2)),
        ("MATRIX_4", (0xCF, 3)),
        ("MATRIX_5", (0xCF, 4)),
        ("MATRIX_6", (0xCF, 5)),
        ("MATRIX_7", (0xCF, 6)),
        ("MATRIX_8", (0xCF, 7)),
        ("MATRIX_9", (0xD0, 0)),
        ("MATRIX_10", (0xD0, 1)),
        ("MATRIX_11", (0xD0, 2)),
        ("MATRIX_12", (0xD0, 3)),
        ("MATRIX_13", (0xD0, 4)),
        ("MATRIX_14", (0xD0, 5)),
        ("MATRIX_15", (0xD0, 6)),
        ("MATRIX_16", (0xD0, 7)),
        ("PERSONAL_1", (0xD1, 0)),
        ("PERSONAL_2", (0xD1, 1)),
        ("PERSONAL_3", (0xD1, 2)),
        ("PERSONAL_4", (0xD1, 3)),
        ("PERSONAL_5", (0xD1, 4)),
        ("PERSONAL_6", (0xD1, 5)),
        ("PERSONAL_7", (0xD1, 6)),
        ("PERSONAL_8", (0xD1, 7)),
        ("TV.ON", (0xD2, 0)),
        ("MUSIC.ON", (0xD3, 0)),
        ("PATTERNPLAY", (0xD3, 1)),
    ]
)

beoremoteone_keydict = OrderedDict(
    [
        (0x0C, "Standby"),
        # Digits:
        (0x00, "Digit-0"),
        (0x01, "Digit-1"),
        (0x02, "Digit-2"),
        (0x03, "Digit-3"),
        (0x04, "Digit-4"),
        (0x05, "Digit-5"),
        (0x06, "Digit-6"),
        (0x07, "Digit-7"),
        (0x08, "Digit-8"),
        (0x09, "Digit-9"),
        # Source control:
        (0x1E, "Step Up"),
        (0x1F, "Step Down"),
        (0x32, "Rewind"),
        (0x33, "Return"),
        (0x34, "Wind"),
        (0x35, "Go/Play"),
        (0x36, "Stop"),
        (0xD4, "Yellow"),
        (0xD5, "Green"),
        (0xD8, "Blue"),
        (0xD9, "Red"),
        # Sound and picture control
        (0x0D, "Mute"),
        (0x1C, "P.Mute"),
        (0x2A, "Format"),
        (0x44, "Sound/Speaker"),
        (0x5C, "Menu"),
        (0x60, "Volume Up"),
        (0x64, "Volume Down"),
        (0xDA, "Cinema_On"),
        (0xDB, "Cinema_Off"),
        # Other controls:
        (0x7C, "Status"),   # ??? 0x5D ???
        (0xF7, "Stand"),
        (0x0A, "Clear"),
        (0x0B, "Store"),
        (0x0E, "Reset"),
        (0x14, "Back"),
        (0x15, "MOTS"),
        (0x20, "Goto"),
        (0x28, "Show Clock"),
        (0x2D, "Eject"),
        (0x37, "Record"),
        (0x3F, "Select"),
        (0x46, "Sound"),
        (0x7F, "Exit"),
        (0xC0, "Shift-0/Edit"),
        (0xC1, "Shift-1/Random"),
        (0xC2, "Shift-2"),
        (0xC3, "Shift-3/Repeat"),
        (0xC4, "Shift-4/Select"),
        (0xC5, "Shift-5"),
        (0xC6, "Shift-6"),
        (0xC7, "Shift-7"),
        (0xC8, "Shift-8"),
        (0xC9, "Shift-9"),
        # Continue functionality:
        (0x70, "Rewind Repeat"),
        (0x71, "Wind Repeat"),
        (0x72, "Step_UP Repeat"),
        (0x73, "Step_DW Repeat"),
        (0x75, "Go Repeat"),
        (0x76, "Green Repeat"),
        (0x77, "Yellow Repeat"),
        (0x78, "Blue Repeat"),
        (0x79, "Red Repeat"),
        (0x7E, "Key Release"),
        # Functions:
        (0xE3, "Home Control"),
        (0x40, "Guide"),
        (0x43, "Info"),
        # Cursor functions:
        (0x13, "Select"),
        (0xCA, "Cursor_Up"),
        (0xCB, "Cursor_Down"),
        (0xCC, "Cursor_Left"),
        (0xCD, "Cursor_Right"),
        # Light/Control commands
        (0x9B, "Light"),
        (0x9C, "Command"),
        (0x58, "Light Timeout")
    ]
)

# ########################################################################################
# Source Activity
sourceactivitydict = OrderedDict(
    [
        (0x00, "Unknown"),
        (0x01, "Stop"),
        (0x02, "Play"),
        (0x03, "Wind"),
        (0x04, "Rewind"),
        (0x05, "Record Lock"),
        (0x06, "Standby"),
        (0x07, "Load/No Media"),
        (0x08, "Still Picture"),
        (0x14, "Scan Forward"),
        (0x15, "Scan Reverse"),
        (0xFF, "None"),
    ]
)

# ########################################################################################
# ##### MasterLink (not MLGW)  Protocol packet constants
ml_telegram_type_dict = dict(
    [
        (0x0A, "COMMAND"),
        (0x0B, "REQUEST"),
        (0x14, "RESPONSE"),
        (0x2C, "INFO"),
        (0x5E, "CONFIG"),
    ]
)

ml_command_type_dict = dict(
    [
        (0x04, "MASTER_PRESENT"),
        # REQUEST_DISTRIBUTED_SOURCE: seen when a device asks what source is being distributed
        # subtypes seen 01:request 04:no source 06:has source (byte 13 is source)
        (0x08, "REQUEST_DISTRIBUTED_SOURCE"),
        (0x0D, "BEO4_KEY"),
        (0x10, "STANDBY"),
        (0x11, "RELEASE"),  # when a device turns off
        (0x20, "MLGW_REMOTE_BEO4"),
        # REQUEST_LOCAL_SOURCE: Seen when a device asks what source is playing locally to a device
        # subtypes seen 02:request 04:no source 05:secondary source 06:primary source (byte 11 is source)
        # byte 10 is bitmask for distribution: 0x01: coaxial cable - 0x02: MasterLink ML_BUS -
        #                                      0x08: local screen
        (0x30, "REQUEST_LOCAL_SOURCE"),
        (0x3C, "TIMER"),
        (0x40, "CLOCK"),
        (0x44, "TRACK_INFO"),
        (0x45, "GOTO_SOURCE"),
        # LOCKMANAGER_COMMAND: Lock to Determine what device issues source commands
        # reference: https://tidsskrift.dk/daimipb/article/download/7043/6004/0
        (0x5C, "LOCK_MANAGER_COMMAND"),
        (0x6C, "DISTRIBUTION_REQUEST"),
        (0x82, "TRACK_INFO_LONG"),
        # Source Status
        # byte 10:source - byte 13: 80 when DTV is turned off. 00 when it's on
        # byte 18H 17L: source medium - byte 19: channel/track - byte 21:activity
        # byte 22: 01: audio source 02: video source ff:undefined - byte 23: picture identifier
        (0x87, "STATUS_INFO"),
        (0x94, "VIDEO_TRACK_INFO"),
        #
        # -----------------------------------------------------------------------
        # More packets that we see on the bus, with a guess of the type
        # DISPLAY_SOURCE: Message sent with a payload showing the displayed source name.
        # subtype 3 has the printable source name starting at byte 10 of the payload
        (0x06, "DISPLAY_SOURCE"),
        # START_VIDEO_DISTRIBUTION: Sent when a locally playing source starts being distributed on coaxial cable
        (0x07, "START_VIDEO_DISTRIBUTION"),
        # EXTENDED_SOURCE_INFORMATION: message with 6 subtypes showing information about the source.
        # Printable info at byte 14 of the payload
        # For Radio: 1: "" 2: Genre 3: Country 4: RDS info 5: Associated beo4 button 6: "Unknown"
        # For A.Mem: 1: Genre 2: Album 3: Artist 4: Track name 5: Associated beo4 button 6: "Unknown"
        (0x0B, "EXTENDED_SOURCE_INFORMATION"),
        (0x96, "PC_PRESENT"),
        # PICTURE AND SOUND STATUS
        # byte 0: bit 0-1: sound status - bit 2-3: stereo mode (can be 0 in a 5.1 setup)
        # byte 1: speaker mode (see below)
        # byte 2: audio volume
        # byte 3: picture format identifier (see below)
        # byte 4: bit 0: screen1 mute - bit 1: screen2 mute - bit 2: screen1 active -
        #         bit 3: screen2 active - bit 4: cinema mode
        (0x98, "PICTURE_AND_SOUND_STATUS"),
        # Unknown commands - seen on power up and initialisation
        #########################################################
        # On power up all devices send out a request key telegram. If
        # no lock manager is allocated the devices send out a key_lost telegram. The Video Master (or Power
        # Master in older implementations) then asserts a NEW_LOCKMANAGER telegram and assumes responsibility
        # for LOCKMANAGER_COMMAND telegrams until a key transfer occurs.
        # reference: https://tidsskrift.dk/daimipb/article/download/7043/6004/0
        (0x12, "KEY_LOST"),  # ?
        # Unknown command with payload of length 1.
        # bit 0: unknown
        # bit 1: unknown
        (0xA0, "NEW_LOCKMANAGER"),  # ?
        # Unknown command with payload of length 2
        # bit 0: unknown
        # bit 1: unknown
        # bit 2: unknown
    ]
)

ml_command_type_request_key_subtype_dict = dict(
    [
        (0x01, "Request Key"),
        (0x02, "Transfer Key"),
        (0x03, "Transfer Impossible"),
        (0x04, "Key Received"),
        (0x05, "Timeout"),
        (0xFF, "Undefined"),
    ]
)

ml_activity_dict = dict(
    [
        (0x01, "Request Source"),
        (0x02, "Request Source"),
        (0x04, "No Source"),
        (0x06, "Source Active"),
    ]
)

ml_device_dict = dict(
    [
        (0xC0, "VIDEO MASTER"),
        (0xC1, "AUDIO MASTER"),
        (0xC2, "SOURCE CENTER/SLAVE DEVICE"),
        (0x81, "ALL AUDIO LINK DEVICES"),
        (0x82, "ALL VIDEO LINK DEVICES"),
        (0x83, "ALL LINK DEVICES"),
        (0x80, "ALL"),
        (0xF0, "MLGW"),
        (0x29, "SYSTEM CONTROLLER/TIMER"),
        # Power Master exists in older (pre 1996?) ML implementations. Later revisions enforced the Video Master
        # as lock key manager for the system and the concept was phased out. If your system is older than 2000
        # you may see this device type on the network.
        # reference: https://tidsskrift.dk/daimipb/article/download/7043/6004/0
        (0xFF, "POWER MASTER"),  # ?
    ]
)

ml_pictureformatdict = dict(
    [
        (0x00, "Not known"),
        (0x01, "Known by decoder"),
        (0x02, "4:3"),
        (0x03, "16:9"),
        (0x04, "4:3 Letterbox middle"),
        (0x05, "4:3 Letterbox top"),
        (0x06, "4:3 Letterbox bottom"),
        (0xFF, "Blank picture"),
    ]
)

ml_selectedsourcedict = dict(
    [
        (0x00, "NONE"),
        (0x0B, "TV"),
        (0x15, "V.TAPE/V.MEM"),
        (0x16, "DVD2"),
        (0x1F, "SAT/DTV"),
        (0x29, "DVD"),
        (0x33, "V.AUX/DTV2"),
        (0x3E, "DOORCAM"),
        (0x47, "PC"),
        (0x6F, "RADIO"),
        (0x79, "A.TAPE/A.MEM"),
        (0x7A, "A.TAPE2/N.MUSIC"),
        (0x8D, "CD"),
        (0x97, "A.AUX"),
        (0xA1, "PHONO/N.RADIO"),
        #  Dummy for 'Listen for all sources'
        (0xFE, "ALL"),  # have also seen 0xFF as "all"
        (0xFF, "ALL"),
    ]
)

ml_trackinfo_subtype_dict = dict([(0x05, "Current Source"), (0x07, "Change Source"), ])

ml_sourcekind_dict = dict([(0x01, "audio source"), (0x02, "video source"), (0xFF, "undefined")])

# ########################################################################################
# ##### MLGW Protocol packet constants
mlgw_payloadtypedict = dict(
    [
        (0x01, "Beo4 Command"),
        (0x02, "Source Status"),
        (0x03, "Picture and Sound Status"),
        (0x04, "Light and Control command"),
        (0x05, "All standby notification"),
        (0x06, "BeoRemote One control command"),
        (0x07, "BeoRemote One source selection"),
        (0x20, "MLGW virtual button event"),
        (0x30, "Login request"),
        (0x31, "Login status"),
        (0x32, "Change password request"),
        (0x33, "Change password response"),
        (0x34, "Secure login request"),
        (0x36, "Ping"),
        (0x37, "Pong"),
        (0x38, "Configuration change notification"),
        (0x39, "Request Serial Number"),
        (0x3A, "Serial Number"),
        (0x40, "Location based event"),
    ]
)
MLGW_PL = {v.upper(): k for k, v in mlgw_payloadtypedict.items()}

destselectordict = OrderedDict(
    [
        (0x00, "Video Source"),
        (0x01, "Audio Source"),
        (0x05, "Peripheral Video Source (V.TAPE/V.MEM/DVD)"),
        (0x06, "Secondary Peripheral Video Source (V.TAPE2/V.MEM2/DVD2)"),
        (0x0F, "All Products"),
        (0x1B, "MLGW"),
    ]
)
CMDS_DEST = {v.upper(): k for k, v in destselectordict.items()}

mlgw_secsourcedict = dict([(0x00, "V.TAPE/V.MEM"), (0x01, "V.TAPE2/DVD2/V.MEM2")])
mlgw_linkdict = dict([(0x00, "Local/Default Source"), (0x01, "Remote Source/Option 4 Product")])

mlgw_virtualactiondict = dict([(0x01, "PRESS"), (0x02, "HOLD"), (0x03, "RELEASE")])

# for '0x03: Picture and Sound Status'
mlgw_soundstatusdict = dict([(0x00, "Not muted"), (0x01, "Muted")])

mlgw_speakermodedict = dict(
    [
        (0x01, "Center channel"),
        (0x02, "2 channel stereo"),
        (0x03, "Front surround"),
        (0x04, "4 channel stereo"),
        (0x05, "Full surround"),
        (0xFD, "<all>"),            # Dummy for 'Listen for all modes'
    ]
)

mlgw_screenmutedict = dict([(0x00, "not muted"), (0x01, "muted")])
mlgw_screenactivedict = dict([(0x00, "not active"), (0x01, "active")])
mlgw_cinemamodedict = dict([(0x00, "Cinema mode off"), (0x01, "Cinema mode on")])
mlgw_stereoindicatordict = dict([(0x00, "Mono"), (0x01, "Stereo")])

# for '0x04: Light and Control command'
mlgw_lctypedict = dict([(0x01, "LIGHT"), (0x02, "CONTROL")])

# for '0x31: Login Status
mlgw_loginstatusdict = dict([(0x00, "OK"), (0x01, "FAIL")])

# ########################################################################################
# ##### BeoLink Gateway Protocol packet constants
blgw_srcdict = dict(
    [
        ("TV", "TV"),
        ("DVD", "DVD"),
        ("RADIO", "RADIO"),
        ("TP1", "A.TAPE/A.MEM"),
        ("TP2", "A.TAPE2/N.MUSIC"),
        ("CD", "CD"),
        ("PH", "PHONO/N.RADIO"),
    ]
)

blgw_devtypes = OrderedDict(
    [
        ("*", "All"),
        ("SYSTEM", "System"),
        ("AV renderer", "AV Renderer"),
        ("BUTTON", "Button"),
        ("Dimmer", "Dimmer"),
        ("GPIO", "GPIO"),
        ("Thermostat 1 setpoint", "Thermostat 1 setpoint"),
        ("Thermostat 2 setpoints", "Thermostat 2 setpoints")
    ]
)
