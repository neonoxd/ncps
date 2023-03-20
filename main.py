import glob
import sys
import os.path
import subprocess
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
	def __init__(self, opts: list, display_fields=None):
		if display_fields is None:
			display_fields = [0]
		self.choice_i = -1
		self.choice = None
		if len(opts) == 0:
			return

		X_OFFSET = 12

		stdscr = curses.initscr()
		curses.cbreak()
		curses.noecho()
		try:
			YMAX, XMAX = stdscr.getmaxyx()
			MAX_LCHARS = XMAX - X_OFFSET

			menuwin = curses.newwin(YMAX - 4, XMAX - X_OFFSET, 2, 6)
			menuwin.box(0, 0)
			stdscr.refresh()
			menuwin.refresh()
			menuwin.keypad(True)

			n_choices = len(opts)
			highlight = 0
			choice_made = False

			while not choice_made:
				for i in range(n_choices):
					if i == highlight:
						menuwin.attron(curses.A_REVERSE)

					used_length = 0
					for field_i in range(len(display_fields)):
						raw_str = opts[i][display_fields[field_i]]
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
				elif pressed == 27:
					curses.endwin()
					exit(0)
				elif pressed == 10:
					choice_made = True
					choice = highlight
					self.choice_i = choice
					self.choice = opts[choice]

				menuwin.addstr(0, 1, str(highlight))
				menuwin.addstr(0, 20, "   ")
				menuwin.addstr(0, 20, str(pressed))
				menuwin.refresh()
				stdscr.refresh()
		except:
			pass
		finally:
			curses.endwin()

	def get_choice_i(self):
		return self.choice_i

	def get_choice(self):
		return self.choice


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


if __name__ == "__main__":
	main()
