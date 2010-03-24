/*
 * Copyright 2007, Intel Corporation
 *
 * This file is part of PowerTOP
 *
 * This program file is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; version 2 of the License.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
 * for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program in a file named COPYING; if not, write to the
 * Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor,
 * Boston, MA 02110-1301 USA
 *
 * Authors:
 * 	Arjan van de Ven <arjan@linux.intel.com>
 */


#ifndef __INCLUDE_GUARD_POWERTOP_H_
#define __INCLUDE_GUARD_POWERTOP_H_

#include <libintl.h>

struct line {
	char	*string;
	int	count;
	char 	pid[12];
};

typedef void (suggestion_func)(void);

extern struct line     *lines;  
extern int             linehead;
extern int             linesize;
extern int             linectotal;

extern double displaytime;

void suggest_process_death(char *process_match, char *process_name, struct line *slines, int linecount, double minwakeups, char *comment, int weight);
void suggest_kernel_config(char *string, int onoff, char *comment, int weight);
void suggest_laptop_mode(void);
void suggest_bluetooth_off(void);
void suggest_nmi_watchdog(void);
void suggest_hpet(void);
void suggest_ac97_powersave(void);
void suggest_wireless_powersave(void);
void suggest_ondemand_governor(void);
void suggest_noatime(void);
void suggest_sata_alpm(void);
void suggest_powersched(void);
void suggest_xrandr_TV_off(void);
void suggest_WOL_off(void);
void suggest_writeback_time(void);
void suggest_usb_autosuspend(void);
void usb_activity_hint(void);




extern char cstate_lines[12][200];
extern char cpufreqstrings[6][80];

extern int topcstate;
extern int topfreq;  
extern int dump;

extern int showpids;

extern char status_bar_slots[10][40];
extern char suggestion_key;
extern suggestion_func *suggestion_activate; 


/* min definition borrowed from the Linux kernel */
#define min(x,y) ({ \
        typeof(x) _x = (x);     \
        typeof(y) _y = (y);     \
        (void) (&_x == &_y);            \
        _x < _y ? _x : _y; })


#define _(STRING)    gettext(STRING)


#define PT_COLOR_DEFAULT    1
#define PT_COLOR_HEADER_BAR 2
#define PT_COLOR_ERROR      3
#define PT_COLOR_RED        4
#define PT_COLOR_YELLOW     5
#define PT_COLOR_GREEN      6
#define PT_COLOR_BRIGHT     7
#define PT_COLOR_BLUE	    8
extern int maxwidth;

void show_title_bar(void);
void setup_windows(void);
void initialize_curses(void);
void show_acpi_power_line(double rate, double cap, double capdelta, time_t time);
void show_pmu_power_line(unsigned sum_voltage_mV,
                         unsigned sum_charge_mAh, unsigned sum_max_charge_mAh,
                         int sum_discharge_mA);
void show_cstates(void);
void show_wakeups(double d, double interval, double c0time);
void show_timerstats(int nostats, int ticktime);
void show_suggestion(char *sug);

void pick_suggestion(void);
void add_suggestion(char *text, int weight, char key, char *keystring, suggestion_func *func);
void reset_suggestions(void);
void print_all_suggestions(void);
void push_line(char *string, int count);

void  do_cpufreq_stats(void);
void count_usb_urbs(void);

void display_usb_activity(void);
void activate_usb_autosuspend(void);
void print_intel_cstates(void);


#endif
