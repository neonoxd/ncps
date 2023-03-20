import glob
import sys
import os.path
import subprocess
import traceback
from dataclasses import dataclass
from pathlib import Path

import vdf
import curses

steam_root = os.getenv("STEAM_HOME", os.path.join(os.getenv("HOME"), ".steam/root"))


@dataclass
class ProtonEnv:
	PROTON: str = None
	PATHEXTRA: str = None
	WINEPREFIX: str = None
	WINESERVER: str = None
	WINELOADER: str = None
	WINEDLLPATH: str = None

	def todict(self):
		return {
			"PROTON": self.PROTON,
			"PATHEXTRA": self.PATHEXTRA,
			"WINEPREFIX": self.WINEPREFIX,
			"WINESERVER": self.WINESERVER,
			"WINELOADER": self.WINELOADER,
			"WINEDLLPATH": self.WINEDLLPATH
		}


class CMenu:
	def __init__(self, list_options: list, display_fields=None):
		if display_fields is None:
			display_fields = [0]
		self.choice_i = -1
		self.choice = None

		if len(list_options) == 0:
			return

		X_OFFSET = 12


		stdscr = curses.initscr()
		curses.cbreak()
		curses.noecho()

		YMAX, XMAX = stdscr.getmaxyx()
		MAX_LCHARS = XMAX - X_OFFSET
		page_size = YMAX-6

		menuwin = curses.newwin(YMAX - 4, XMAX - X_OFFSET, 2, 6)
		menuwin.box(0, 0)
		stdscr.refresh()
		menuwin.refresh()
		menuwin.keypad(True)

		n_choices = len(list_options)
		highlight = 0
		choice_made = False
		cur_page = 0
		opts_partitioned = list(partition(list_options, page_size))

		while not choice_made:
			act_list = opts_partitioned[cur_page]
			for i in range(len(act_list)):
				if i == highlight:
					menuwin.attron(curses.A_REVERSE)

				used_length = 0
				for field_i in range(len(display_fields)):
					raw_str = act_list[i][display_fields[field_i]]
					cut_str = str(raw_str)[-(MAX_LCHARS-used_length-len(display_fields) - 1):]
					formatted_str = cut_str
					if field_i == len(display_fields) - 1:
						if len(display_fields) == 1:
							formatted_str = cut_str.ljust(MAX_LCHARS - used_length - 3)
						else:
							formatted_str = cut_str.rjust(MAX_LCHARS-used_length-3)
					elif field_i == 0: # FIRST ALWAYS FIX 32W
						formatted_str = raw_str.ljust(24)
					menuwin.addstr(i + 1, used_length + 1, formatted_str)
					used_length += len(formatted_str)

				menuwin.attroff(curses.A_REVERSE)

			pressed = menuwin.getch()

			if pressed == curses.KEY_UP:
				if highlight - 1 < 0:
					highlight = n_choices - 1
				else:
					highlight -= 1
			elif pressed == curses.KEY_DOWN:
				if highlight + 1 == n_choices:
					highlight = 0
				else:
					highlight += 1
			elif pressed == curses.KEY_LEFT:
				cur_page -= 1
			elif pressed == curses.KEY_RIGHT:
				cur_page += 1
			elif pressed == 27:
				curses.endwin()
				exit(0)
			elif pressed == 10:
				choice_made = True
				choice = highlight
				self.choice_i = choice
				self.choice = list_options[(cur_page * page_size) + choice]

			menuwin.addstr(0, 1, str(highlight))
			menuwin.addstr(0, 20, "   ")
			menuwin.addstr(0, 20, str(pressed))
			menuwin.refresh()
			stdscr.refresh()
			curses.endwin()

	def get_choice_i(self):
		return self.choice_i

	def get_choice(self):
		return self.choice


def partition(lst, size):
	for i in range(0, len(lst), size):
		yield lst[i: i+size]


def lower_dict(d):
	"""
		do be stolen
	"""
	def _lower_value(value):
		if not isinstance(value, dict):
			return value

		return {k.lower(): _lower_value(v) for k, v in value.items()}

	return {k.lower(): _lower_value(v) for k, v in d.items()}


def find_proton_dirs():
	common_path = os.path.join(steam_root, "steamapps", "common")
	comptools_path = os.path.join(steam_root, "compatibilitytools.d")

	found_dirs = list(filter(os.path.isdir, glob.glob(comptools_path + "/*")))
	found_dirs += list(filter(os.path.isdir, glob.glob(common_path + "/Proton*")))
	found_dirs.sort(key=lambda x: os.path.getmtime(x))

	proton_dirs = []

	for dir in found_dirs:
		p1p = os.path.join(dir, "files")
		p1 = os.path.isdir(p1p)
		p2p = os.path.join(dir, "dist")
		p2 = os.path.isdir(p2p)
		if p1 or p2:
			proton_dirs.append((os.path.basename(dir), dir, p1p if p1 else p2p))

	return proton_dirs


def find_compat_dirs():
	cdata_path = os.path.join(steam_root, "steamapps", "compatdata")
	files = list(filter(os.path.isdir, glob.glob(cdata_path + "/*")))
	files.sort(key=lambda x: os.path.getmtime(x))

	scs = parse_shortcuts()

	dirs = []
	for comp_dir in files:
		appid = os.path.basename(comp_dir)
		appname = "UNKNOWN"
		manifest_path = os.path.join(steam_root, "steamapps", f"appmanifest_{appid}.acf")
		if appid in scs:
			appname = scs[appid]
		elif os.path.isfile(manifest_path):
			with open(manifest_path, "r") as manifest_file:
				lines = manifest_file.readlines()
				appname_line = list(filter(lambda x: "name" in x, lines))
				try:
					appname = appname_line[0].split("\t")[-1][1:-2]
				except:
					pass
		else:
			pass
		dirs.append((appid, appname, comp_dir))
	return dirs


def parse_shortcuts():
	shortcutpaths = find_shortcuts()
	shortcut_map = {}

	for scp in shortcutpaths:
		#print(f"READING SC: {scp}")
		content = Path(scp).read_bytes()
		vdf_data = lower_dict(vdf.binary_loads(content))

		for shortcut_id, shortcut_data in vdf_data["shortcuts"].items():
			shortcut_data = lower_dict(shortcut_data)
			if "appid" in shortcut_data:
				appid = shortcut_data['appid'] & 0xffffffff
				shortcut_map[str(appid)] = shortcut_data['appname']
				#print(f"{appid} - {shortcut_data['appname']}")
	return shortcut_map


def find_shortcuts():
	udata_path = os.path.join(steam_root, "userdata")
	shortcuts = list(filter(os.path.isfile, glob.glob(udata_path + "/*/config/shortcuts.vdf")))
	return [os.path.abspath(sc) for sc in shortcuts]


def main():
	fpd = find_proton_dirs()
	fcd = find_compat_dirs()

	if len(sys.argv) < 2:
		print(f"{len(fpd)} proton dirs found")
		print(f"{len(fcd)} compat dirs found")
		print("proton dirs:")
		print("\n".join([d[1] for d in fpd]))
		exit(0)

	proton_choice = CMenu(fpd, [0, 1]).get_choice()
	compat_choice = CMenu(fcd, [0, 1, 2]).get_choice()

	if None in [proton_choice, compat_choice]:
		return

	pEnv = ProtonEnv(
		PROTON=proton_choice[1],
		WINEPREFIX=os.path.join(compat_choice[2], "pfx"),
		PATHEXTRA=os.path.join(proton_choice[2], "bin"),
		WINESERVER=os.path.join(proton_choice[2], "wineserver"),
		WINELOADER=os.path.join(proton_choice[2], "wine"),
		WINEDLLPATH=os.path.join(proton_choice[2], "lib", "wine") + ":" + os.path.join(proton_choice[2], "lib64", "wine")
	)
	print(pEnv)

	os_env = dict(os.environ)
	os_env.update(pEnv.todict())
	print("------------- END OF NCPS -------------")

	p = subprocess.Popen([*sys.argv[1:]], env=os_env)
	p.communicate()


data = [('1887720', 'Proton 7.0', '/home/deck/.steam/root/steamapps/compatdata/1887720'), ('570940', 'DARK SOULS™: REMASTERED', '/home/deck/.steam/root/steamapps/compatdata/570940'), ('1493710', 'Proton Experimental', '/home/deck/.steam/root/steamapps/compatdata/1493710'), ('12210', 'Grand Theft Auto IV: The Complete Edition', '/home/deck/.steam/root/steamapps/compatdata/12210'), ('1133590', 'Stilt Fella', '/home/deck/.steam/root/steamapps/compatdata/1133590'), ('4129048096', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/4129048096'), ('881100', 'Noita', '/home/deck/.steam/root/steamapps/compatdata/881100'), ('1442820', 'R-Type Final 2', '/home/deck/.steam/root/steamapps/compatdata/1442820'), ('418530', 'Spelunky 2', '/home/deck/.steam/root/steamapps/compatdata/418530'), ('501590', 'Bulletstorm: Full Clip Edition', '/home/deck/.steam/root/steamapps/compatdata/501590'), ('4240451690.off', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/4240451690.off'), ('4240451690.clean', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/4240451690.clean'), ('3874078589', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/3874078589'), ('2658327321', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/2658327321'), ('3667314027', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/3667314027'), ('2483586634', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/2483586634'), ('2630', 'Call of Duty 2', '/home/deck/.steam/root/steamapps/compatdata/2630'), ('600130', 'Valfaris', '/home/deck/.steam/root/steamapps/compatdata/600130'), ('2433259615', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/2433259615'), ('1253920', 'Rogue Legacy 2', '/home/deck/.steam/root/steamapps/compatdata/1253920'), ('3146476534', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/3146476534'), ('2807485917', 'Need For Speed The Run', '/home/deck/.steam/root/steamapps/compatdata/2807485917'), ('2790457296', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/2790457296'), ('396900', 'GRIP: Combat Racing', '/home/deck/.steam/root/steamapps/compatdata/396900'), ('1148590', 'DOOM 64', '/home/deck/.steam/root/steamapps/compatdata/1148590'), ('4240451690', 'Gears of War', '/home/deck/.steam/root/steamapps/compatdata/4240451690'), ('962730', 'Skater XL', '/home/deck/.steam/root/steamapps/compatdata/962730'), ('217200', 'Worms Armageddon', '/home/deck/.steam/root/steamapps/compatdata/217200'), ('996580', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/996580'), ('3030208529', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/3030208529'), ('632360', 'Risk of Rain 2', '/home/deck/.steam/root/steamapps/compatdata/632360'), ('24960', 'Battlefield: Bad Company™ 2', '/home/deck/.steam/root/steamapps/compatdata/24960'), ('1245040', 'Proton 5.0', '/home/deck/.steam/root/steamapps/compatdata/1245040'), ('631510', 'Devil May Cry HD Collection', '/home/deck/.steam/root/steamapps/compatdata/631510'), ('244210.ge18', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/244210.ge18'), ('244210.fuk', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/244210.fuk'), ('244210.ge20-cmfucked', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/244210.ge20-cmfucked'), ('244210.baknew', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/244210.baknew'), ('244210.latest', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/244210.latest'), ('244210.ge20shit', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/244210.ge20shit'), ('1245620', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/1245620'), ('803330', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/803330'), ('6570', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/6570'), ('339340', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/339340'), ('2000330', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/2000330'), ('50300', 'Spec Ops: The Line', '/home/deck/.steam/root/steamapps/compatdata/50300'), ('12130', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/12130'), ('1110910', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/1110910'), ('1580130', 'Proton 6.3', '/home/deck/.steam/root/steamapps/compatdata/1580130'), ('2310', 'Quake', '/home/deck/.steam/root/steamapps/compatdata/2310'), ('221100', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/221100'), ('287310', 'Re-Volt', '/home/deck/.steam/root/steamapps/compatdata/287310'), ('646570', 'Slay the Spire', '/home/deck/.steam/root/steamapps/compatdata/646570'), ('17470', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/17470'), ('893680', 'Project Warlock', '/home/deck/.steam/root/steamapps/compatdata/893680'), ('732810', 'Slipstream', '/home/deck/.steam/root/steamapps/compatdata/732810'), ('238370', 'Magicka 2', '/home/deck/.steam/root/steamapps/compatdata/238370'), ('34270', 'SEGA Mega Drive & Genesis Classics', '/home/deck/.steam/root/steamapps/compatdata/34270'), ('1222680', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/1222680'), ('1328660', 'Need for Speed™ Hot Pursuit Remastered', '/home/deck/.steam/root/steamapps/compatdata/1328660'), ('460790', 'Bayonetta', '/home/deck/.steam/root/steamapps/compatdata/460790'), ('321040', 'DiRT 3 Complete Edition', '/home/deck/.steam/root/steamapps/compatdata/321040'), ('587620', 'Okami HD', '/home/deck/.steam/root/steamapps/compatdata/587620'), ('1301010', 'World Racing 2', '/home/deck/.steam/root/steamapps/compatdata/1301010'), ('2198740', 'One Wheel Guy', '/home/deck/.steam/root/steamapps/compatdata/2198740'), ('28000', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/28000'), ('219150', 'Hotline Miami', '/home/deck/.steam/root/steamapps/compatdata/219150'), ('0', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/0'), ('8190', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/8190'), ('1145360', 'Hades', '/home/deck/.steam/root/steamapps/compatdata/1145360'), ('635260', 'CarX Drift Racing Online', '/home/deck/.steam/root/steamapps/compatdata/635260'), ('1088710', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/1088710'), ('244210', 'UNKNOWN', '/home/deck/.steam/root/steamapps/compatdata/244210'), ('730', 'Counter-Strike: Global Offensive', '/home/deck/.steam/root/steamapps/compatdata/730'), ('3864221111', 'Startup.exe', '/home/deck/.steam/root/steamapps/compatdata/3864221111')]
CMenu(data, [0, 1, 2])

if __name__ == "__main__":
	pass
	#main()

