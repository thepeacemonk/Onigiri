/* icon_chooser.js */

var currentSelectedIcon = null;
var currentSelectedColor = "#888888";
var systemIcons = {}; // Store system icon URLs
var currentMode = "icon"; // 'icon' or 'emoji'
var accentColor = "#007aff";
var colorWasModified = false;

var commonEmojis = [
    "😀", "😃", "😄", "😁", "😆", "😅", "😂", "🤣", "😊", "😇", "🙂", "🙃", "😉", "😌", "😍", "🥰",
    "😘", "😗", "😙", "😚", "😋", "😛", "😝", "😜", "🤪", "🤨", "🧐", "🤓", "😎", "🤩", "🥳", "😏",
    "😒", "😞", "😔", "😕", "🙁", "☹️", "😣", "😖", "😫", "😩", "🥺", "😢", "😭", "😤", "😠", "😡",
    "🤬", "🤯", "😳", "🥵", "🥶", "😱", "😨", "😰", "😥", "😓", "🤗", "🤔", "🤭", "🤫", "🤥", "😶",
    "😐", "😑", "😬", "🙄", "😯", "😦", "😧", "😮", "😲", "🥱", "😴", "🤤", "😪", "😵", "🤐", "🥴",
    "🤢", "🤮", "🤧", "😷", "🤒", "🤕", "🤑", "🤠", "😈", "👿", "👹", "👺", "🤡", "💩", "👻", "💀",
    "☠️", "👽", "👾", "🤖", "🎃", "😺", "😸", "😹", "😻", "😼", "😽", "🙀", "😿", "😾", "👋", "🤚",
    "🖐", "✋", "🖖", "👌", "🤏", "✌️", "🤞", "🤟", "🤘", "🤙", "👈", "👉", "👆", "🖕", "👇", "☝️",
    "👍", "👎", "✊", "👊", "🤛", "🤜", "👏", "🙌", "👐", "🤲", "🤝", "🙏", "✍️", "💅", "🤳", "💪",
    "🧠", "🦴", "👀", "👁", "🗣", "👤", "👥", "👶", "👧", "🧒", "👦", "👩", "🧑", "👨", "👩‍🦱", "🧑‍🦱",
    "👨‍🦱", "👩‍🦰", "🧑‍🦰", "👨‍🦰", "👱‍♀️", "👱", "👱‍♂️", "👩‍🦳", "🧑‍🦳", "👨‍🦳", "👩‍🦲", "🧑‍🦲", "👨‍🦲", "🧔", "👵",
    "🧓", "👴", "👲", "👳‍♀️", "👳", "👳‍♂️", "🧕", "👮‍♀️", "👮", "👮‍♂️", "👷‍♀️", "👷", "👷‍♂️", "💂‍♀️", "💂", "💂‍♂️",
    "🕵️‍♀️", "🕵", "🕵️‍♂️", "👩‍⚕️", "🧑‍⚕️", "👨‍⚕️", "👩‍🌾", "🧑‍🌾", "👨‍🌾", "👩‍🍳", "🧑‍🍳", "👨‍🍳", "👩‍🎓", "🧑‍🎓", "👨‍🎓",
    "👩‍🎤", "🧑‍🎤", "👨‍🎤", "👩‍🏫", "🧑‍🏫", "👨‍🏫", "👩‍🏭", "🧑‍🏭", "👨‍🏭", "👩‍💻", "🧑‍💻", "👨‍💻", "👩‍💼", "🧑‍💼",
    "👨‍💼", "👩‍🔧", "🧑‍🔧", "👨‍🔧", "👩‍🔬", "🧑‍🔬", "👨‍🔬", "👩‍🎨", "🧑‍🎨", "👨‍🎨", "👩‍🚒", "🧑‍🚒", "👨‍🚒", "👩‍✈️",
    "🧑‍✈️", "👨‍✈️", "👩‍🚀", "🧑‍🚀", "👨‍🚀", "👩‍⚖️", "🧑‍⚖️", "👨‍⚖️", "👰", "🤵", "👸", "🤴", "🦸‍♀️", "🦸", "🦸‍♂️",
    "🦹‍♀️", "🦹", "🦹‍♂️", "🤶", "🎅", "🧙‍♀️", "🧙", "🧙‍♂️", "🧝‍♀️", "🧝", "🧝‍♂️", "🧛‍♀️", "🧛", "🧛‍♂️", "🧟‍♀️", "🧟",
    "🧟‍♂️", "🧞‍♀️", "🧞", "🧞‍♂️", "🧜‍♀️", "🧜", "🧜‍♂️", "🧚‍♀️", "🧚", "🧚‍♂️", "👼", "🤰", "🤱", "🙇‍♀️", "🙇",
    "🙇‍♂️", "💁‍♀️", "💁", "💁‍♂️", "🙅‍♀️", "🙅", "🙅‍♂️", "🙆‍♀️", "🙆", "🙆‍♂️", "🙋‍♀️", "🙋", "🙋‍♂️", "🧏‍♀️", "🧏",
    "🧏‍♂️", "🤦‍♀️", "🤦", "🤦‍♂️", "🤷‍♀️", "🤷", "🤷‍♂️", "🙎‍♀️", "🙎", "🙎‍♂️", "🙍‍♀️", "🙍", "🙍‍♂️", "💇‍♀️", "💇",
    "💇‍♂️", "💆‍♀️", "💆", "💆‍♂️", "🧖‍♀️", "🧖", "🧖‍♂️", "💃", "🕺", "👯‍♀️", "👯", "👯‍♂️", "🕴", "🚶‍♀️", "🚶",
    "🚶‍♂️", "🏃‍♀️", "🏃", "🏃‍♂️", "🧍‍♀️", "🧍", "🧍‍♂️", "🧎‍♀️", "🧎", "🧎‍♂️", "👨‍🦯", "👩‍🦯", "👨‍🦼", "👩‍🦼", "👨‍🦽",
    "👩‍🦽", "🏃‍♀️", "🏃", "🏃‍♂️", "🧘‍♀️", "🧘", "🧘‍♂️", "🛀", "🛌", "👭", "👫", "👬", "💏", "💑", "👨‍👩‍👦",
    "👨‍👩‍👧", "👨‍👩‍👧‍👦", "👨‍👩‍👦‍👦", "👨‍👩‍👧‍👧", "👨‍👨‍👦", "👨‍👨‍👧", "👨‍👨‍👧‍👦", "👨‍👨‍👦‍👦", "👨‍👨‍👧‍👧", "👩‍👩‍👦", "👩‍👩‍👧", "👩‍👩‍👧‍👦", "👩‍👩‍👦‍👦",
    "👩‍👩‍👧‍👧", "🧵", "🧶", "🧥", "🥼", "👚", "👕", "👖", "🩲", "🩳", "👔", "👗", "👙", "👘", "🥻", "🩱",
    "🥿", "👠", "👡", "👢", "👞", "👟", "🥾", "🧦", "🧤", "🧣", "🎩", "🧢", "👒", "🎓", "⛑", "👑", "💍",
    "👝", "👛", "👜", "💼", "🎒", "👓", "🕶", "🥽", "🌂", "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻",
    "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐽", "🐸", "🐵", "🙈", "🙉", "🙊", "🐒", "🐔", "🐧", "🐦",
    "🐤", "🐣", "🐥", "🦆", "🦅", "🦉", "🦇", "🐺", "🐗", "🐴", "🦄", "🐝", "🐛", "🦋", "🐌", "🐞",
    "🐜", "🦟", "🦗", "🕷", "🕸", "🦂", "🐢", "🐍", "🦎", "🦖", "🦕", "🐙", "🦑", "🦐", "🦞", "🦀",
    "🐡", "🐠", "🐟", "🐬", "🐳", "🐋", "🦈", "🐊", "🐅", "🐆", "🦓", "🦍", "🦧", "🐘", "🦛", "🦏",
    "🐪", "🐫", "🦒", "🦘", "🐃", "🐂", "🐄", "🐎", "🐖", "🐏", "🐑", "🦙", "🐐", "🦌", "🐕", "🐩",
    "🦮", "🐕‍🦺", "🐈", "🐓", "🦃", "🦚", "🦜", "🦢", "🦩", "🕊", "🐇", "🦝", "🦨", "🦡", "🦦", "🦥",
    "🐁", "🐀", "🐿", "🦔", "🐾", "🐉", "🐲", "🌵", "🎄", "🌲", "🌳", "🌴", "🌱", "🌿", "☘️", "🍀",
    "🎍", "🎋", "🍃", "🍂", "🍁", "🍄", "🐚", "🌾", "💐", "🌷", "🌹", "🥀", "🌺", "🌸", "🌼", "🌻",
    "🌞", "🌝", "🌛", "🌜", "🌚", "🌕", "🌖", "🌗", "🌘", "🌑", "🌒", "🌓", "🌔", "🌙", "🌎", "🌍",
    "🌏", "🪐", "💫", "⭐️", "🌟", "✨", "⚡️", "☄️", "💥", "🔥", "🌪", "🌈", "☀️", "🌤", "⛅️", "🌥",
    "☁️", "🌦", "🌧", "⛈", "🌩", "🌨", "❄️", "☃️", "⛄️", "🌬", "💨", "💧", "💦", "☔️", "☂️", "🌊",
    "🌫", "🍏", "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍈", "🍒", "🍑", "🥭", "🍍", "🥥",
    "🥝", "🍅", "🍆", "🥑", "🥦", "🥬", "🥒", "🌶", "🌽", "🥕", "🧄", "🧅", "🥔", "🍠", "🥐", "🥯",
    "🍞", "🥖", "🥨", "🧀", "🥚", "🍳", "🧈", "🥞", "🧇", "🥓", "🥩", "🍗", "🍖", "🦴", "🌭", "🍔",
    "🍟", "🍕", "🥪", "🥙", "🧆", "🌮", "🌯", "🥗", "🥘", "🥫", "🍝", "🍜", "🍲", "🍛", "🍣", "🍱",
    "🥟", "🦪", "🍤", "🍙", "🍚", "🍘", "🍥", "🥠", "🍢", "🍡", "🍧", "🍨", "🍦", "🥧", "🧁", "🍰",
    "🎂", "🍮", "🍭", "🍬", "🍫", "🍿", "🍩", "🍪", "🌰", "🥜", "🍯", "🥛", "🍼", "☕️", "🍵", "🧃",
    "🥤", "🍶", "🍺", "🍻", "🥂", "🍷", "🥃", "🍸", "🍹", "🧉", "🍾", "🧊", "🥄", "🍴", "🍽", "🥣",
    "🥡", "🥢", "🧂", "⚽️", "🏀", "🏈", "⚾️", "🥎", "🎾", "🏐", "🏉", "🥏", "🎱", "🪀", "🏓", "🏸",
    "🏒", "🏑", "🥍", "🏏", "🥅", "⛳️", "🪁", "🏹", "🎣", "🤿", "🥊", "🥋", "🎽", "🛹", "🛷", "⛸",
    "🥌", "🎿", "⛷", "🏂", "🪂", "🏋️‍♀️", "🏋", "🏋️‍♂️", "🤼‍♀️", "🤼", "🤼‍♂️", "🤸‍♀️", "🤸", "🤸‍♂️", "⛹️‍♀️", "⛹",
    "⛹️‍♂️", "🤺", "🤾‍♀️", "🤾", "🤾‍♂️", "🏌️‍♀️", "🏌", "🏌️‍♂️", "🏇", "🧘‍♀️", "🧘", "🧘‍♂️", "🏄‍♀️", "🏄", "🏄‍♂️",
    "🏊‍♀️", "🏊", "🏊‍♂️", "🤽‍♀️", "🤽", "🤽‍♂️", "🚣‍♀️", "🚣", "🚣‍♂️", "🧗‍♀️", "🧗", "🧗‍♂️", "🚵‍♀️", "🚵",
    "🚵‍♂️", "🚴‍♀️", "🚴", "🚴‍♂️", "🏆", "🥇", "🥈", "🥉", "🏅", "🎖", "🏵", "🎗", "🎫", "🎟", "🎪",
    "🤹‍♀️", "🤹", "🤹‍♂️", "🎭", "🩰", "🎨", "🎬", "🎤", "🎧", "🎼", "🎹", "🥁", "🎷", "🎺", "🎸", "🪕",
    "🎻", "🎲", "🧩", "♟", "🎯", "🎳", "🎮", "🎰", "🚗", "🚕", "🚙", "🚌", "🚎", "🏎", "🚓", "🚑",
    "🚒", "🚐", "🚚", "🚛", "🚜", "🦯", "🦽", "🦼", "🛴", "🚲", "🛵", "🏍", "🛺", "🚨", "🚔", "🚍",
    "🚘", "🚖", "🚡", "🚠", "🚟", "🚃", "🚋", "🚞", "🚝", "🚄", "🚅", "🚈", "🚂", "🚆", "🚇", "🚊",
    "🚉", "✈️", "🛫", "🛬", "🛩", "💺", "🛰", "🚀", "🛸", "🚁", "🛶", "⛵️", "🚤", "🛥", "🛳", "⛴",
    "🚢", "⚓️", "⛽️", "🚧", "🚦", "🚥", "🚏", "🗺", "🗿", "🗽", "🗼", "🏰", "🏯", "🏟", "🎡", "🎢",
    "🎠", "⛲️", "⛱", "🏖", "🏝", "🏜", "🌋", "⛰", "🏔", "🗻", "🏕", "⛺️", "🏠", "🏡", "🏘", "🏚",
    "🏗", "🏭", "🏢", "🏬", "🏣", "🏤", "🏥", "🏦", "🏨", "🏪", "🏫", "🏩", "💒", "🏛", "⛪️", "🕌",
    "🕍", "🛕", "🕋", "⛩", "🛤", "🛣", "🗾", "🎑", "🏞", "🌅", "🌄", "🌠", "🎇", "🎆", "🌇", "🌆",
    "🏙", "🌃", "🌌", "🌉", "🌁", "⌚️", "📱", "📲", "💻", "⌨️", "🖥", "🖨", "🖱", "🖲", "🕹", "🗜",
    "💽", "💾", "💿", "📀", "📼", "📷", "📸", "📹", "🎥", "📽", "🎞", "📞", "☎️", "📟", "📠", "📺",
    "📻", "🎙", "🎚", "🎛", "🧭", "⏱", "⏲", "⏰", "🕰", "⌛️", "⏳", "📡", "🔋", "🔌", "💡", "🔦",
    "🕯", "🪔", "🧯", "🛢", "💸", "💵", "💴", "💶", "💷", "💰", "💳", "💎", "⚖️", "🧰", "🔧", "🔨",
    "⚒", "🛠", "⛏", "🪓", "🔩", "⚙️", "🧱", "⛓", "🧲", "🔫", "💣", "🧨", "🪓", "🔪", "🗡", "⚔️",
    "🛡", "🚬", "⚰️", "⚱️", "🏺", "🔮", "📿", "🧿", "💈", "⚗️", "🔭", "🔬", "🕳", "🩹", "🩺", "💊",
    "💉", "🩸", "🧬", "🦠", "🧫", "🧪", "🌡", "🧹", "🧺", "🧻", "🚽", "🚰", "🚿", "🛁", "🛀", "🧼",
    "🪒", "🧽", "🧴", "🛎", "🔑", "🗝", "🚪", "🪑", "🛋", "🛏", "🛌", "🧸", "🖼", "🛍", "🛒", "🎁",
    "🎈", "🎏", "🎀", "🎊", "🎉", "🎎", "🏮", "🎐", "🧧", "✉️", "📩", "📨", "📧", "💌", "📥", "📤",
    "📦", "🏷", "📪", "📫", "📬", "📭", "📮", "📯", "📜", "📃", "📄", "📑", "🧾", "📊", "📈", "📉",
    "🗒", "🗓", "📆", "📅", "🗑", "📇", "🗃", "🗳", "🗄", "📋", "📁", "📂", "🗂", "🗞", "📰", "📓",
    "📔", "📒", "📕", "📗", "📘", "📙", "📚", "📖", "🔖", "🔗", "📎", "🖇", "📐", "📏", "🧮", "📌",
    "📍", "✂️", "🖊", "🖋", "✒️", "🖌", "🖍", "📝", "✏️", "🔍", "🔎", "🔏", "🔐", "🔒", "🔓", "❤️",
    "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "❣️", "💕", "💞", "💓", "💗", "💖", "💘",
    "💝", "💟", "☮️", "✝️", "☪️", "🕉", "☸️", "✡️", "🔯", "🕎", "☯️", "☦️", "🛐", "⛎", "♈️", "♉️",
    "♊️", "♋️", "♌️", "♍️", "♎️", "♏️", "♐️", "♑️", "♒️", "♓️", "🆔", "⚛️", "🉑", "☢️", "☣️", "📴",
    "📳", "🈶", "🈚️", "🈸", "🈺", "🈷️", "✴️", "🆚", "💮", "🉐", "㊙️", "㊗️", "🈴", "🈵", "🈹", "🈲",
    "🅰️", "🅱️", "🆎", "🆑", "🅾️", "🆘", "❌", "⭕️", "🛑", "⛔️", "📛", "🚫", "💯", "💢", "♨️", "🚷",
    "🚯", "🚳", "🚱", "🔞", "📵", "🚭", "❗️", "❕", "❓", "❔", "‼️", "⁉️", "🔅", "🔆", "〽️", "⚠️",
    "🚸", "🔱", "⚜️", "🔰", "♻️", "✅", "🈯️", "💹", "❇️", "✳️", "❎", "🌐", "💠", "Ⓜ️", "🌀", "💤",
    "🏧", "🚾", "♿️", "🅿️", "🈳", "🈂️", "🛂", "🛃", "🛄", "🛅", "🚹", "🚺", "🚼", "🚻", "🚮", "🎦",
    "📶", "🈁", "🔣", "ℹ️", "🔤", "🔡", "🔠", "🆖", "🆗", "🆙", "🆒", "🆕", "🆓", "0️⃣", "1️⃣", "2️⃣",
    "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "🔢", "#️⃣", "*️⃣", "⏏️", "▶️", "⏸", "⏯",
    "⏹", "⏺", "⏭", "⏮", "⏩", "⏪", "⏫", "⏬", "◀️", "🔼", "🔽", "➡️", "⬅️", "⬆️", "⬇️", "↗️",
    "↘️", "↙️", "↖️", "↕️", "↔️", "↪️", "↩️", "⤴️", "⤵️", "🔀", "🔁", "🔂", "🔄", "🔃", "🎵", "🎶",
    "➕", "➖", "➗", "✖️", "♾", "💲", "💱", "™️", "©️", "®️", "👁‍🗨", "🔚", "🔙", "🔛", "🔝", "🔜",
    "〰️", "➰", "➿", "✔️", "☑️", "🔘", "🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "⚫️", "⚪️", "🟤", "🔺",
    "🔻", "🔸", "🔹", "🔶", "🔷", "🔳", "🔲", "▪️", "▫️", "◾️", "◽️", "◼️", "◻️", "🟥", "🟧", "🟨",
    "🟩", "🟦", "🟪", "⬛️", "⬜️", "🟫", "🔈", "🔇", "🔉", "🔊", "🔔", "🔕", "📣", "📢", "💬", "💭",
    "🗯", "♠️", "♣️", "♥️", "♦️", "🃏", "🎴", "🀄️", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗",
    "🕘", "🕙", "🕚", "🕛", "🕜", "🕝", "🕞", "🕟", "🕠", "🕡", "🕢", "🕣", "🕤", "🕥", "🕦", "🕧"
];

// Color picker state (using HSV color space for proper gradient behavior)
var colorPickerState = {
    hue: 0,
    saturation: 100,
    value: 100,
    alpha: 100,
    isDraggingGradient: false,
    isDraggingHue: false,
    isDraggingAlpha: false
};

function clampByte(value) {
    return Math.max(0, Math.min(255, Math.round(value)));
}

function channelToHex(value) {
    var hex = clampByte(value).toString(16).toUpperCase();
    return hex.length === 1 ? "0" + hex : hex;
}

function rgbaToHex(r, g, b, a) {
    var base = "#" + channelToHex(r) + channelToHex(g) + channelToHex(b);
    var alpha = typeof a === "number" ? clampByte(a) : 255;
    return alpha < 255 ? base + channelToHex(alpha) : base;
}

function parseColorValue(value) {
    if (typeof value !== "string") return null;
    var text = value.trim();
    if (!text) return null;

    var hexMatch = text.match(/^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/);
    if (hexMatch) {
        var digits = hexMatch[1];
        if (digits.length === 3 || digits.length === 4) {
            digits = digits.split("").map(function (ch) { return ch + ch; }).join("");
        }
        if (digits.length === 6) {
            return {
                r: parseInt(digits.slice(0, 2), 16),
                g: parseInt(digits.slice(2, 4), 16),
                b: parseInt(digits.slice(4, 6), 16),
                a: 255
            };
        }
        return {
            r: parseInt(digits.slice(0, 2), 16),
            g: parseInt(digits.slice(2, 4), 16),
            b: parseInt(digits.slice(4, 6), 16),
            a: parseInt(digits.slice(6, 8), 16)
        };
    }

    var rgbMatch = text.match(/^rgba?\((.+)\)$/i);
    if (rgbMatch) {
        var parts = rgbMatch[1].split(",").map(function (part) { return part.trim(); });
        if (parts.length === 3 || parts.length === 4) {
            var r = parseFloat(parts[0]);
            var g = parseFloat(parts[1]);
            var b = parseFloat(parts[2]);
            if (!isNaN(r) && !isNaN(g) && !isNaN(b)) {
                var alpha = 255;
                if (parts.length === 4) {
                    var alphaValue = parts[3];
                    if (/%$/.test(alphaValue)) {
                        alpha = clampByte(parseFloat(alphaValue) * 2.55);
                    } else {
                        var alphaFloat = parseFloat(alphaValue);
                        if (!isNaN(alphaFloat)) {
                            alpha = alphaFloat <= 1 ? clampByte(alphaFloat * 255) : clampByte(alphaFloat);
                        }
                    }
                }
                return { r: clampByte(r), g: clampByte(g), b: clampByte(b), a: alpha };
            }
        }
    }

    return null;
}

function normalizeColorValue(value, fallback) {
    var parsed = parseColorValue(value);
    if (parsed) return rgbaToHex(parsed.r, parsed.g, parsed.b, parsed.a);
    if (fallback) return normalizeColorValue(fallback);
    return null;
}

function colorToCss(value) {
    var parsed = typeof value === "string" ? parseColorValue(value) : value;
    if (!parsed) return "#888888";
    if (parsed.a >= 255) {
        return rgbaToHex(parsed.r, parsed.g, parsed.b, 255);
    }
    var alpha = (parsed.a / 255).toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
    if (!alpha) alpha = "0";
    return "rgba(" + parsed.r + ", " + parsed.g + ", " + parsed.b + ", " + alpha + ")";
}

// Wait for pycmd to be available
function waitForBridge(callback, attempts) {
    if (typeof pycmd === 'function') {
        callback();
    } else if (attempts > 0) {
        setTimeout(function () { waitForBridge(callback, attempts - 1); }, 50);
    } else {
        console.error("Icon Chooser: pycmd never became available");
        var grid = document.getElementById("icon-grid");
        if (grid) grid.innerHTML = '<div style="color: red; padding: 20px;">Error: Bridge not available.</div>';
    }
}

function initApp() {
    // Use pre-injected data if available (avoids bridge round-trip timing issues).
    // Python injects window.ONIGIRI_ICON_INIT into the page <head>.
    if (window.ONIGIRI_ICON_INIT) {
        updateData(window.ONIGIRI_ICON_INIT);
    } else {
        // Fallback: request data via bridge
        pycmd("get_init_data");
    }

    // Initialize color picker
    initColorPicker();

    // Bind all button handlers
    var resetBtn = document.getElementById("reset-btn");
    var saveBtn = document.getElementById("save-btn");
    var cancelBtn = document.getElementById("cancel-btn");
    var addIconBtn = document.getElementById("add-icon-btn");
    var togglePickerBtn = document.getElementById("icon-color-btn");

    if (resetBtn) {
        resetBtn.onclick = function () {
            pycmd("reset");
        };
    }

    if (saveBtn) {
        saveBtn.onclick = function () {
            if (currentSelectedIcon !== null && currentSelectedIcon !== undefined) {
                var colorToSave = (currentSelectedIcon === "" && !colorWasModified) ? "" : currentSelectedColor;
                var payload = JSON.stringify({ icon: currentSelectedIcon, color: colorToSave });
                pycmd("save:" + payload);
            } else {
                alert("Please select an icon first.");
            }
        };
    }

    if (cancelBtn) {
        cancelBtn.onclick = function () {
            pycmd("cancel");
        };
    }

    if (addIconBtn) {
        addIconBtn.onclick = function () {
            pycmd("add_icon");
        };
    }

    if (togglePickerBtn) {
        togglePickerBtn.onclick = function () {
            var panel = document.getElementById("color-picker-panel");
            if (panel) {
                panel.classList.toggle("hidden");
                // Rotation logic removed as we don't have an arrow anymore, 
                // but could add active state style if desired
            }
        };
    }

    // Toggle Mode Logic
    var toggleOptions = document.querySelectorAll(".toggle-option");
    toggleOptions.forEach(function (opt) {
        opt.onclick = function () {
            var mode = opt.dataset.mode;
            setMode(mode);
        };
    });

}

window.updateData = function (data) {
    if (data.system_icons) {
        systemIcons = data.system_icons;
    }
    if (data.accentColor) {
        accentColor = data.accentColor;
        document.documentElement.style.setProperty('--accent-color', accentColor);
    }

    loadedIcons = data.icons || [];
    loadedImages = data.images || [];

    var currentIcon = data.current.icon;
    currentSelectedIcon = currentIcon; // Sync state

    // Determine mode: Priority to explicit mode from backend (e.g. after upload)
    if (data.mode) {
        if (data.mode === "icon") {
            setMode("icon");
            // Also render emoji grid in background just in case
            renderEmojiGrid();
        } else if (data.mode === "image") {
            setMode("image");
        } else if (data.mode === "emoji") {
            renderEmojiGrid(currentIcon);
            setMode("emoji");
        }
    } else {
        // Fallback: Determine mode based on current icon
        if (currentIcon && currentIcon.toLowerCase().endsWith(".png")) {
            setMode("image");
        } else if (currentIcon && currentIcon.length <= 8 && currentIcon.indexOf('.') === -1 && currentIcon !== "") {
            renderEmojiGrid(currentIcon);
            setMode("emoji");
        } else {
            // Default to icon mode (SVG or empty)
            renderEmojiGrid(); // Just render emoji grid in background
            setMode("icon");
        }
    }

    colorWasModified = false;
    updateColor(data.current.color || "#888888");
    applyColorToSelectedIcon();
};

var loadedIcons = [];
var loadedImages = [];

function setMode(mode) {
    currentMode = mode;

    // Toggle body classes safely
    document.body.classList.remove("mode-icon", "mode-emoji", "mode-image");
    document.body.classList.add("mode-" + mode);

    document.querySelectorAll(".toggle-option").forEach(function (el) {
        if (el.dataset.mode === mode) el.classList.add("selected");
        else el.classList.remove("selected");
    });

    if (mode === "emoji") {
        document.getElementById("color-picker-panel").classList.add("hidden");
    } else if (mode === "image") {
        renderGrid(loadedImages, currentSelectedIcon, "image");
    } else {
        // Icon mode
        renderGrid(loadedIcons, currentSelectedIcon, "icon");
    }
}

function renderEmojiGrid(selectedEmoji) {
    var grid = document.querySelector(".emoji-grid");
    if (!grid) {
        // Create if doesn't exist (it should from CSS/HTML updates, but safety check)
        var mainContent = document.querySelector(".main-content");
        grid = document.createElement("div");
        grid.className = "emoji-grid";
        mainContent.appendChild(grid);
    }
    // ... existing emoji rendering code is fine, but I'm rewriting this block ...
    // To minimize replacement size, I will try to leave renderEmojiGrid alone if possible, 
    // but the task boundary suggests I'm replacing a chunk.
    // Actually, I can just keep renderEmojiGrid as is if I don't touch it.
    // The replacement range handles renderEmojiGrid, so I must include it or be careful with lines.

    // Rerendering Emoji Grid
    grid.innerHTML = "";

    commonEmojis.forEach(function (emoji) {
        var item = document.createElement("div");
        item.className = "emoji-item";
        item.textContent = emoji;

        if (emoji === selectedEmoji) {
            item.classList.add("selected");
            // Scroll to it
            setTimeout(function () { item.scrollIntoView({ block: "center" }); }, 100);
        }

        item.onclick = function () {
            selectEmoji(emoji, item);
        };

        grid.appendChild(item);
    });
}

function selectEmoji(emoji, element) {
    currentSelectedIcon = emoji;

    var items = document.querySelectorAll(".emoji-item");
    items.forEach(function (i) { i.classList.remove("selected"); });
    element.classList.add("selected");

}

function renderGrid(itemsList, selectedIconName, type) {
    var grid = document.getElementById("icon-grid");
    if (!grid) return;

    grid.innerHTML = "";
    // Don't overwrite currentSelectedIcon here unless determining initial state
    // currentSelectedIcon = selectedIconName; 

    // Create "Add" card
    var addCard = document.createElement("div");
    addCard.className = "icon-item add-icon-card";

    var addAction = (type === "image") ? "add_image" : "add_icon";
    var addLabel = (type === "image") ? "Add Image" : "Add Icon";

    addCard.onclick = function () { pycmd(addAction); };

    var addImgContainer = document.createElement("div");
    addImgContainer.className = "icon-img-container";
    var addImg = document.createElement("img");
    addImg.src = systemIcons.add || "";
    addImg.className = "icon-img add-icon-img";
    addImgContainer.appendChild(addImg);

    var addText = document.createElement("div");
    addText.className = "icon-name";
    addText.textContent = addLabel;
    addText.style.fontWeight = "bold";

    addCard.appendChild(addImgContainer);
    addCard.appendChild(addText);
    grid.appendChild(addCard);

    // Default icon card (represents the built-in placeholder — always shown in icon mode)
    if (type === "icon") {
        var defaultCard = document.createElement("div");
        defaultCard.className = "icon-item default-icon-card";
        if (selectedIconName === "") {
            defaultCard.classList.add("selected");
        }
        defaultCard.dataset.name = "";
        defaultCard.onclick = function () { selectIcon("", defaultCard, "icon"); };

        var defaultImgContainer = document.createElement("div");
        defaultImgContainer.className = "icon-img-container";
        var defaultImg = document.createElement("img");
        defaultImg.src = systemIcons.default_deck || "";
        defaultImg.className = "icon-img";
        defaultImgContainer.appendChild(defaultImg);

        var defaultText = document.createElement("div");
        defaultText.className = "icon-name";
        defaultText.textContent = "Default";

        defaultCard.appendChild(defaultImgContainer);
        defaultCard.appendChild(defaultText);
        grid.appendChild(defaultCard);
    }

    if (!itemsList || itemsList.length === 0) {
        return;
    }

    itemsList.forEach(function (itemData) {
        var item = document.createElement("div");
        item.className = "icon-item";
        if (itemData.name === selectedIconName) {
            item.classList.add("selected");
        }
        item.dataset.name = itemData.name;
        item.onclick = function () { selectIcon(itemData.name, item, type); };

        var imgContainer = document.createElement("div");
        imgContainer.className = "icon-img-container";

        var img = document.createElement("img");
        img.src = itemData.url;
        img.className = "icon-img";
        if (type === "image") {
            img.classList.add("original-color");
        }

        img.onerror = function () { console.error("Failed to load: " + itemData.url); };
        imgContainer.appendChild(img);

        // Delete button
        var delBtn = document.createElement("div");
        delBtn.className = "delete-icon-btn";
        var delImg = document.createElement("img");
        delImg.src = systemIcons.delete || "";
        delBtn.appendChild(delImg);

        delBtn.onclick = function (e) {
            e.stopPropagation();
            showConfirmModal(
                "Delete " + (type === "image" ? "Image" : "Icon") + "?",
                "Are you sure you want to delete '" + itemData.name + "'? This action cannot be undone.",
                function () {
                    pycmd("delete_icon:" + itemData.name);
                }
            );
        };

        item.appendChild(imgContainer);
        item.appendChild(delBtn);
        grid.appendChild(item);
    });
}

function selectIcon(name, element, type) {
    currentSelectedIcon = name;
    var items = document.querySelectorAll(".icon-item");
    for (var i = 0; i < items.length; i++) {
        items[i].classList.remove("selected");
    }
    element.classList.add("selected");

    // Apply current color to newly selected icon ONLY if it's an SVG icon
    if (type === "icon") {
        applyColorToSelectedIcon();
    }
}

function updateColor(hex) {
    currentSelectedColor = normalizeColorValue(hex, currentSelectedColor || "#888888") || "#888888";
    var cssColor = colorToCss(currentSelectedColor);
    var preview = document.getElementById("color-preview-large");
    if (preview) preview.style.backgroundColor = cssColor;

    // Update button preview as well
    var btnPreview = document.getElementById("btn-color-preview");
    if (btnPreview) {
        btnPreview.style.backgroundColor = cssColor;
        btnPreview.style.color = cssColor;
    }

    var hexInput = document.getElementById("hex-input");
    if (hexInput) hexInput.value = currentSelectedColor;

    // Update HSV state from the normalized value
    var hsv = hexToHSV(currentSelectedColor);
    colorPickerState.hue = hsv.h;
    colorPickerState.saturation = hsv.s;
    colorPickerState.value = hsv.v;
    colorPickerState.alpha = hsv.a;

    updateColorPickerUI();

    // Apply color to selected icon for real-time preview
    if (currentMode === "icon") {
        applyColorToSelectedIcon();
    }
}

function applyColorToSelectedIcon() {
    // Find the selected icon item
    var selectedItem = document.querySelector(".icon-item.selected");
    if (!selectedItem) return;

    var iconImg = selectedItem.querySelector(".icon-img");
    if (!iconImg) return;

    iconImg.style.filter = "brightness(0) saturate(100%) drop-shadow(0 0 0 " + colorToCss(currentSelectedColor) + ")";
}

function hexToRGB(hex) {
    var parsed = parseColorValue(hex);
    return parsed ? {
        r: parsed.r,
        g: parsed.g,
        b: parsed.b,
        a: parsed.a
    } : { r: 136, g: 136, b: 136, a: 255 };
}

// ===== COLOR PICKER FUNCTIONS =====

function initColorPicker() {
    // Gradient selector
    var gradientSelector = document.getElementById("gradient-selector");
    if (gradientSelector) {
        gradientSelector.addEventListener("mousedown", function (e) {
            colorPickerState.isDraggingGradient = true;
            updateGradientPosition(e);
        });
    }

    // Hue slider
    var hueSlider = document.getElementById("hue-slider");
    if (hueSlider) {
        hueSlider.addEventListener("mousedown", function (e) {
            colorPickerState.isDraggingHue = true;
            updateHuePosition(e);
        });
    }

    var alphaSlider = document.getElementById("alpha-slider");
    if (alphaSlider) {
        alphaSlider.addEventListener("mousedown", function (e) {
            colorPickerState.isDraggingAlpha = true;
            updateAlphaPosition(e);
        });
    }

    // Global mouse events
    document.addEventListener("mousemove", function (e) {
        if (colorPickerState.isDraggingGradient) {
            updateGradientPosition(e);
        } else if (colorPickerState.isDraggingHue) {
            updateHuePosition(e);
        } else if (colorPickerState.isDraggingAlpha) {
            updateAlphaPosition(e);
        }
    });

    document.addEventListener("mouseup", function () {
        colorPickerState.isDraggingGradient = false;
        colorPickerState.isDraggingHue = false;
        colorPickerState.isDraggingAlpha = false;
    });

    // Hex input
    var hexInput = document.getElementById("hex-input");
    if (hexInput) {
        hexInput.addEventListener("input", function (e) {
            var value = e.target.value.replace(/[^#0-9A-Fa-f]/g, "");
            if (value && value.charAt(0) !== "#") {
                value = "#" + value.replace(/#/g, "");
            } else if (value) {
                value = "#" + value.slice(1).replace(/#/g, "");
            }
            if (value.length > 9) {
                value = value.slice(0, 9);
            }
            if (value !== e.target.value) {
                e.target.value = value;
            }

            var normalized = normalizeColorValue(value);
            if (normalized) {
                updateColor(normalized);
                notifyColorChange(normalized);
            }
        });
        hexInput.addEventListener("blur", function () {
            hexInput.value = currentSelectedColor || "#888888";
        });
        hexInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                hexInput.blur();
            }
        });
    }
}

function updateGradientPosition(e) {
    var gradientSelector = document.getElementById("gradient-selector");
    if (!gradientSelector) return;

    var rect = gradientSelector.getBoundingClientRect();
    var x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    var y = Math.max(0, Math.min(e.clientY - rect.top, rect.height));

    // X-axis: saturation (0% left, 100% right)
    // Y-axis: value/brightness (100% top, 0% bottom)
    var saturation = (x / rect.width) * 100;
    var value = 100 - (y / rect.height) * 100;

    colorPickerState.saturation = saturation;
    colorPickerState.value = value;

    updateColorFromHSV();
}

function updateHuePosition(e) {
    var hueSlider = document.getElementById("hue-slider");
    if (!hueSlider) return;

    var rect = hueSlider.getBoundingClientRect();
    var x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    var hue = (x / rect.width) * 360;

    colorPickerState.hue = hue;
    updateColorFromHSV();
    updateGradientBackground();
}

function updateAlphaPosition(e) {
    var alphaSlider = document.getElementById("alpha-slider");
    if (!alphaSlider) return;

    var rect = alphaSlider.getBoundingClientRect();
    var x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    colorPickerState.alpha = (x / rect.width) * 100;
    updateColorFromHSV();
}

function updateColorFromHSV() {
    var alpha = clampByte((colorPickerState.alpha / 100) * 255);
    var hex = hsvToHex(colorPickerState.hue, colorPickerState.saturation, colorPickerState.value, alpha);
    currentSelectedColor = hex;
    var cssColor = colorToCss(hex);

    var preview = document.getElementById("color-preview-large");
    if (preview) preview.style.backgroundColor = cssColor;

    var btnPreview = document.getElementById("btn-color-preview");
    if (btnPreview) {
        btnPreview.style.backgroundColor = cssColor;
        btnPreview.style.color = cssColor;
    }

    var hexInput = document.getElementById("hex-input");
    if (hexInput) hexInput.value = hex;

    updateColorPickerUI();
    if (currentMode === "icon") {
        applyColorToSelectedIcon();
    }
    notifyColorChange(hex);
}

function updateColorPickerUI() {
    // Update gradient cursor position
    var gradientCursor = document.getElementById("gradient-cursor");
    if (gradientCursor) {
        var x = colorPickerState.saturation;
        var y = 100 - colorPickerState.value;
        gradientCursor.style.left = x + "%";
        gradientCursor.style.top = y + "%";
    }

    // Update hue thumb position
    var hueThumb = document.getElementById("hue-thumb");
    if (hueThumb) {
        var huePercent = (colorPickerState.hue / 360) * 100;
        hueThumb.style.left = huePercent + "%";
    }

    var alphaThumb = document.getElementById("alpha-thumb");
    if (alphaThumb) {
        alphaThumb.style.left = colorPickerState.alpha + "%";
    }

    var alphaValue = document.getElementById("alpha-value");
    if (alphaValue) {
        alphaValue.textContent = Math.round(colorPickerState.alpha) + "%";
    }

    updateGradientBackground();
    updateAlphaBackground();
}

function updateGradientBackground() {
    var gradientSelector = document.getElementById("gradient-selector");
    if (gradientSelector) {
        var hueColor = hsvToHex(colorPickerState.hue, 100, 100);
        gradientSelector.style.background = "linear-gradient(to right, " + hueColor + ", " + hueColor + ")";
    }
}

function updateAlphaBackground() {
    var alphaGradient = document.getElementById("alpha-gradient");
    if (!alphaGradient) return;

    var baseColor = parseColorValue(hsvToHex(colorPickerState.hue, colorPickerState.saturation, colorPickerState.value, 255));
    if (!baseColor) return;

    alphaGradient.style.background =
        "linear-gradient(to right, rgba(" + baseColor.r + ", " + baseColor.g + ", " + baseColor.b + ", 0), " +
        "rgba(" + baseColor.r + ", " + baseColor.g + ", " + baseColor.b + ", 1))";
}

function notifyColorChange(hex) {
    colorWasModified = true;
    var normalized = normalizeColorValue(hex, currentSelectedColor || "#888888");
    if (normalized && typeof pycmd === 'function') pycmd("update_color:" + normalized);
}

// ===== COLOR CONVERSION UTILITIES =====

function hsvToHex(h, s, v, alpha) {
    h = h / 360;
    s = s / 100;
    v = v / 100;

    var r, g, b;
    var i = Math.floor(h * 6);
    var f = h * 6 - i;
    var p = v * (1 - s);
    var q = v * (1 - f * s);
    var t = v * (1 - (1 - f) * s);

    switch (i % 6) {
        case 0: r = v; g = t; b = p; break;
        case 1: r = q; g = v; b = p; break;
        case 2: r = p; g = v; b = t; break;
        case 3: r = p; g = q; b = v; break;
        case 4: r = t; g = p; b = v; break;
        case 5: r = v; g = p; b = q; break;
    }

    return rgbaToHex(r * 255, g * 255, b * 255, typeof alpha === "number" ? alpha : 255);
}

function hexToHSV(hex) {
    var parsed = parseColorValue(hex);
    if (!parsed) return { h: 0, s: 0, v: 100, a: 100 };

    var r = parsed.r / 255;
    var g = parsed.g / 255;
    var b = parsed.b / 255;

    var max = Math.max(r, g, b);
    var min = Math.min(r, g, b);
    var h, s, v = max;

    var d = max - min;
    s = max === 0 ? 0 : d / max;

    if (max === min) {
        h = 0;
    } else {
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }

    return {
        h: Math.round(h * 360),
        s: Math.round(s * 100),
        v: Math.round(v * 100),
        a: Math.round((parsed.a / 255) * 100)
    };
}

// Start when DOM is ready
document.addEventListener("DOMContentLoaded", function () {
    if (window.ONIGIRI_ICON_INIT) {
        // Pre-injected init data is available — render immediately, no pycmd wait needed.
        initApp();
    } else {
        // Fallback: data wasn't pre-injected, so gate on the bridge becoming available.
        waitForBridge(initApp, 40);
    }
});

// Modern Confirmation Modal
function showConfirmModal(title, message, onConfirm) {
    // Create overlay
    var overlay = document.createElement("div");
    overlay.className = "confirm-modal-overlay";

    // Create modal
    var modal = document.createElement("div");
    modal.className = "confirm-modal";

    // Title
    var titleEl = document.createElement("div");
    titleEl.className = "confirm-modal-title";
    titleEl.textContent = title;

    // Message
    var messageEl = document.createElement("div");
    messageEl.className = "confirm-modal-message";
    messageEl.textContent = message;

    // Buttons container
    var buttonsEl = document.createElement("div");
    buttonsEl.className = "confirm-modal-buttons";

    // Cancel button
    var cancelBtn = document.createElement("button");
    cancelBtn.className = "confirm-modal-btn confirm-modal-btn-cancel";
    cancelBtn.textContent = "Cancel";
    cancelBtn.onclick = function () {
        document.body.removeChild(overlay);
    };

    // Confirm button
    var confirmBtn = document.createElement("button");
    confirmBtn.className = "confirm-modal-btn confirm-modal-btn-confirm";
    confirmBtn.textContent = "Delete";
    confirmBtn.onclick = function () {
        document.body.removeChild(overlay);
        if (onConfirm) onConfirm();
    };

    // Assemble
    buttonsEl.appendChild(cancelBtn);
    buttonsEl.appendChild(confirmBtn);
    modal.appendChild(titleEl);
    modal.appendChild(messageEl);
    modal.appendChild(buttonsEl);
    overlay.appendChild(modal);

    // Close on overlay click
    overlay.onclick = function (e) {
        if (e.target === overlay) {
            document.body.removeChild(overlay);
        }
    };

    // Add to DOM
    document.body.appendChild(overlay);

    // Focus confirm button
    setTimeout(function () { confirmBtn.focus(); }, 100);
}
