#!/bin/python3
import curses
import glob
import json
import os.path
import subprocess
import sys
import requests
import vdf
from pathlib import Path

VERSION = "0.3"

homedir = os.getenv("HOME", ".")
steam_root = os.getenv("STEAM_HOME", os.path.join(homedir, ".steam/root"))
config_dir = os.path.join(homedir, ".config", "ncps")

appid_full_cache_path = os.path.join(config_dir, "appids.json")
appid_quick_access_cache_path = os.path.join(config_dir, "quick_appids.json")
last_env_path = os.path.join(config_dir, "last.json")


class CMenu:
	"""
		Cursed CursesTM menu wrapper
		Please Don't look
	"""
	def __init__(self, list_options: list, display_fields=None, title=None):
		if display_fields is None:
			display_fields = [0]
		self.choice_i = -1
		self.choice = None

		if len(list_options) == 0:
			return

		stdscr = curses.initscr()
		curses.curs_set(0)
		stdscr.addstr(0, 0, f"ncps v{VERSION}")
		YMAX, XMAX = stdscr.getmaxyx()

		if title:
			stdscr.addstr(1, int(XMAX/2) - int(len(title)/2), f"{title}")

		X_MARGIN = 12
		X_OFFSET = 6
		Y_OFFSET = 2
		Y_MARGIN = 4

		NCOLS = XMAX - X_MARGIN
		NLINES = YMAX - Y_MARGIN

		PAGE_SIZE = NLINES - 2 

		curses.cbreak()
		curses.noecho()
		menuwin = curses.newwin(NLINES, NCOLS, Y_OFFSET, X_OFFSET)
		menuwin.box(0, 0)
		stdscr.refresh()
		menuwin.refresh()
		menuwin.keypad(True)

		_highlight = 0
		_choice_made = False
		_current_page = 0
		_opts_partitioned = list(partition(list_options, PAGE_SIZE))
		_pages = len(_opts_partitioned)
		_pressed = -1

		menuwin.addstr(0, 1, str(_highlight))
		menuwin.addstr(0, 25, f"{_current_page+1}/{_pages}")
		menuwin.refresh()
		stdscr.refresh()

		while not _choice_made:

			act_list = _opts_partitioned[_current_page]
			n_choices = len(act_list)

			# Render
			for i in range(n_choices):
				if i == _highlight:
					menuwin.attron(curses.A_REVERSE)

				used_length = 0
				for field_i in range(len(display_fields)):
					raw_str = act_list[i][display_fields[field_i]]
					cut_str = str(raw_str)[-(NCOLS-used_length-len(display_fields) - 1):]
					formatted_str = cut_str
					if field_i == len(display_fields) - 1:
						if len(display_fields) == 1:
							formatted_str = cut_str.ljust(NCOLS - used_length - 3)
						else:
							formatted_str = cut_str.rjust(NCOLS-used_length-3)
					elif field_i == 0: # FIRST ALWAYS FIX 24W
						formatted_str = raw_str.ljust(24)
					menuwin.addstr(i + 1, used_length + 1, formatted_str)
					used_length += len(formatted_str)

				menuwin.attroff(curses.A_REVERSE)

				if _current_page + 1 == _pages:
					menuwin.clrtobot()

				menuwin.box(0, 0)
				menuwin.addstr(0, 1, str(_highlight))
				menuwin.addstr(0, NCOLS - 3, str(_pressed))
				menuwin.addstr(0, 25, f"{_current_page + 1}/{_pages}")
				menuwin.refresh()
				stdscr.refresh()

			# Handle input
			_pressed = menuwin.getch()  # HALT!%!

			if _pressed == curses.KEY_UP:
				if _highlight - 1 < 0:
					_highlight = n_choices - 1
				else:
					_highlight -= 1
			elif _pressed == 339:
				if _highlight - 5 < 0:
					_highlight = 0
				else:
					_highlight -= 5
			elif _pressed == curses.KEY_HOME:
				_highlight = 0
			elif _pressed == curses.KEY_DOWN:
				if _highlight + 1 == n_choices:
					_highlight = 0
				else:
					_highlight += 1
			elif _pressed == curses.KEY_END:
				_highlight = n_choices - 1
			elif _pressed == 338:
				if _highlight + 5 >= n_choices:
					_highlight = n_choices - 1
				else:
					_highlight += 5
			elif _pressed == curses.KEY_LEFT:
				if _current_page - 1 >= 0:
					_current_page -= 1
					_highlight = 0
			elif _pressed == curses.KEY_RIGHT:
				if _current_page + 1 < _pages:
					_current_page += 1
					_highlight = 0
			elif _pressed in [27, 113]: # esc
				curses.endwin()
				exit(0)
			elif _pressed == 10:
				_choice_made = True
				choice = _highlight
				self.choice_i = choice
				self.choice = list_options[(_current_page * PAGE_SIZE) + choice]
		stdscr.clear()
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


def refresh_appid_cache(force=False):
	print("refreshing appid cache...")
	url = "http://api.steampowered.com/ISteamApps/GetAppList/v0002/?format=json"
	os.makedirs(config_dir, exist_ok=True)
	if force: # or file older than x
		resp = requests.get(url)
		js = json.loads(resp.content.decode())
		with open(appid_full_cache_path, "w") as f:
			f.write(json.dumps(js, indent=2))


def read_quick_cache():
	print("reading quick cache...")
	if os.path.isfile(appid_quick_access_cache_path):
		with open(appid_quick_access_cache_path) as f:
			return json.loads(f.read())
	else:
		return {}


def read_full_cache():
	print("reading full cache...")
	if os.path.isfile(appid_full_cache_path):
		with open(appid_full_cache_path) as f:
			return json.loads(f.read())
	else:
		return {}


def find_proton_dirs():
	common_path = os.path.join(steam_root, "steamapps", "common")
	comptools_path = os.path.join(steam_root, "compatibilitytools.d")

	found_dirs = list(filter(os.path.isdir, glob.glob(comptools_path + "/*")))
	found_dirs += list(filter(os.path.isdir, glob.glob(common_path + "/Proton*")))
	found_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)

	proton_dirs = []

	for act_dir in found_dirs:
		p1p = os.path.join(act_dir, "files")
		p1 = os.path.isdir(p1p)
		p2p = os.path.join(act_dir, "dist")
		p2 = os.path.isdir(p2p)
		if p1 or p2:
			proton_dirs.append((os.path.basename(act_dir), act_dir, p1p if p1 else p2p))

	return proton_dirs


def find_compat_dirs():
	cdata_path = os.path.join(steam_root, "steamapps", "compatdata")
	files = list(filter(os.path.isdir, glob.glob(cdata_path + "/*")))
	files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

	scs = parse_shortcuts()
	aqac = read_quick_cache()
	afc = None
	updated = False

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
		elif appid in aqac:
			appname = aqac[appid]
		else:
			if afc is None:
				afc = read_full_cache()
			if afc != {}:
				all_apps = afc["applist"]["apps"]
				for app_entry in all_apps:
					if str(app_entry["appid"]) == appid and app_entry["name"] != "":
						appname = f'*{app_entry["name"]}'
						aqac[str(app_entry["appid"])] = appname
						updated = True
						break
		dirs.append((appid, appname, comp_dir))
	if aqac != {} and updated:
		print("updating quick cache...")
		with open(appid_quick_access_cache_path, "w") as f:
			f.write(json.dumps(aqac))
	return dirs


def parse_shortcuts():
	shortcutpaths = find_shortcuts()
	shortcut_map = {}

	for scp in shortcutpaths:
		content = Path(scp).read_bytes()
		vdf_data = lower_dict(vdf.binary_loads(content))

		for shortcut_id, shortcut_data in vdf_data["shortcuts"].items():
			shortcut_data = lower_dict(shortcut_data)
			if "appid" in shortcut_data:
				appid = shortcut_data['appid'] & 0xffffffff
				shortcut_map[str(appid)] = shortcut_data['appname']
	return shortcut_map


def find_shortcuts():
	udata_path = os.path.join(steam_root, "userdata")
	shortcuts = list(filter(os.path.isfile, glob.glob(udata_path + "/*/config/shortcuts.vdf")))
	return [os.path.abspath(sc) for sc in shortcuts]


def do_choice(proton_dirs, compat_dirs):
	proton_choice = CMenu(proton_dirs, [0, 1], title="Please select a Proton version to use").get_choice()
	if not proton_choice:
		exit(1)

	compat_choice = CMenu(compat_dirs, [0, 1, 2], title="Please select a prefix to use").get_choice()
	if not compat_choice:
		exit(1)

	return proton_choice, compat_choice


def save_env(ncps_env):
	with open(last_env_path, "w") as f:
		f.write(json.dumps(ncps_env, indent=2))


def load_env(path=None):
	_path = path if path is not None else last_env_path
	with open(_path, "r") as f:
		return json.loads(f.read())


def create_env(proton_choice, compat_choice):
	proton_root = os.path.abspath(proton_choice[1])
	proton_home = os.path.abspath(proton_choice[2])
	prefix_root = os.path.abspath(compat_choice[2])

	return {
		"PROTON": proton_root,
		"WINEPREFIX": os.path.join(prefix_root, "pfx"),
		"PATHEXTRA": os.path.join(proton_home, "bin"),
		"WINESERVER": os.path.join(proton_home, "wineserver"),
		"WINELOADER": os.path.join(proton_home, "wine"),
		"WINEDLLPATH": os.path.join(proton_home, "lib", "wine") + ":" + os.path.join(proton_choice[2], "lib64", "wine"),
		"APPID": compat_choice[0]
	}


def execute_with_env(ncps_env, args, shell_mode=False):
	os_env = dict(os.environ)
	os_env.update(ncps_env)
	p = subprocess.Popen([*args], env=os_env, shell=shell_mode)
	p.communicate()


def main():
	if len(sys.argv) < 2:
		print("ncps: missing command")
		print(f"usage: {os.path.basename(sys.argv[0])} [-c] command")
		print("------------------------")

		proton_dirs = find_proton_dirs()
		compat_dirs = find_compat_dirs()
		print(f"{len(proton_dirs)} Proton dirs found")
		print(f"{len(compat_dirs)} prefix dirs found")
		if len(compat_dirs):
			print("last prefixes created:")
			print("\t"+"\n\t".join([f"{d[0]} - {d[1]}" for d in compat_dirs][:3]))
			exit(0)
	else:
		if sys.argv[1] == "-r":
			refresh_appid_cache(True)
			find_compat_dirs()
			exit(0)

		proton_dirs = find_proton_dirs()
		compat_dirs = find_compat_dirs()

		proton_choice, compat_choice = do_choice(proton_dirs, compat_dirs)

		ncps_env = create_env(proton_choice, compat_choice)

		save_env(ncps_env)

		if sys.argv[1] == "-c":
			execute_with_env(ncps_env, sys.argv[2:], True)
		else:
			execute_with_env(ncps_env, sys.argv[1:])


if __name__ == "__main__":
	main()
