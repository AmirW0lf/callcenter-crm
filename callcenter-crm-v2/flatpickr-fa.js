(function (global, factory) {
    typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
    typeof define === 'function' && define.amd ? define(['exports'], factory) :
    (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.fa = {}));
})(this, (function (exports) { 'use strict';

    /*! *****************************************************************************
    Copyright (c) Microsoft Corporation.

    Permission to use, copy, modify, and/or distribute this software for any
    purpose with or without fee is hereby granted.

    THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
    REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
    AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
    INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
    LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
    OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
    PERFORMANCE OF THIS SOFTWARE.
    ***************************************************************************** */
    /* global Reflect, Promise */

    var extendStatics = function(d, b) {
        extendStatics = Object.setPrototypeOf ||
            ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
            function (d, b) { for (var p in b) if (Object.prototype.hasOwnProperty.call(b, p)) d[p] = b[p]; };
        return extendStatics(d, b);
    };

    function __extends(d, b) {
        extendStatics(d, b);
        function __() { this.constructor = d; }
        d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
    }

    var Jalalidate = /** @class */ (function (_super) {
        __extends(Jalalidate, _super);
        function Jalalidate(year, month, day, hours, minutes, seconds, miliseconds) {
            _super.call(this) || this;
            // Set the prototype explicitly.
            var self = {};
            Object.setPrototypeOf(self, Jalalidate.prototype);
            self.g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
            self.j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
            self.gregoriandate = new Date();
            self.jalalidate = [];
            if (year !== undefined) {
                switch (typeof year) {
                    case "string":
                        self.gregoriandate = new Date(year);
                        break;
                    case "object":
                        if (year instanceof Jalalidate)
                            self.gregoriandate = new Date(year.gregoriandate.getTime());
                        else if (year instanceof Date)
                            self.gregoriandate = new Date(year.getTime());
                        break;
                    case "number":
                        if (month === undefined) {
                            self.gregoriandate.setTime(year);
                        }
                        else {
                            if (day === undefined)
                                day = 1;
                            if (year == 1900 || year == 2099)
                                self.gregoriandate.setFullYear(year, month, day);
                            else
                                self.setFullYear(year, month, day);
                            if (hours === undefined)
                                hours = 0;
                            if (minutes === undefined)
                                minutes = 0;
                            if (seconds === undefined)
                                seconds = 0;
                            if (miliseconds === undefined)
                                miliseconds = 0;
                            self.setHours(hours, minutes, seconds, miliseconds);
                        }
                        break;
                }
            }
            self.setJalali();
            return self;
        }
        Jalalidate.prototype.jalaliToGregorian = function (j_y, j_m, j_d) {
            var self = this;
            var jy = parseInt(String(j_y), 10) - 979;
            var jm = parseInt(String(j_m), 10) - 1;
            var jd = parseInt(String(j_d), 10) - 1;
            var j_day_no = 365 * jy + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4);
            for (var i = 0; i < jm; ++i)
                j_day_no += self.j_days_in_month[i];
            j_day_no += jd;
            var g_day_no = j_day_no + 79;
            var gy = 1600 +
                400 *
                    Math.floor(g_day_no / 146097); /* 146097 = 365*400 + 400/4 - 400/100 + 400/400 */
            g_day_no = g_day_no % 146097;
            var leap = true;
            if (g_day_no >= 36525) {
                /* 36525 = 365*100 + 100/4 */ g_day_no--;
                gy +=
                    100 *
                        Math.floor(g_day_no / 36524); /* 36524 = 365*100 + 100/4 - 100/100 */
                g_day_no = g_day_no % 36524;
                if (g_day_no >= 365)
                    g_day_no++;
                else
                    leap = false;
            }
            gy += 4 * Math.floor(g_day_no / 1461); /* 1461 = 365*4 + 4/4 */
            g_day_no %= 1461;
            if (g_day_no >= 366) {
                leap = false;
                g_day_no--;
                gy += Math.floor(g_day_no / 365);
                g_day_no = g_day_no % 365;
            }
            for (var i = 0; g_day_no >= self.g_days_in_month[i] + (i == 1 && leap ? 1 : 0); i++)
                g_day_no -= self.g_days_in_month[i] + (i == 1 && leap ? 1 : 0);
            var gm = i + 1;
            var gd = g_day_no + 1;
            return [gy, gm, gd];
        };
        Jalalidate.prototype.checkDate = function (j_y, j_m, j_d) {
            var self = this;
            return !(j_y < 0 ||
                j_y > 32767 ||
                j_m < 1 ||
                j_m > 12 ||
                j_d < 1 ||
                j_d >
                    self.j_days_in_month[j_m - 1] +
                        (j_m == 12 && !(((j_y - 979) % 33) % 4) ? 1 : 0));
        };
        Jalalidate.prototype.gregorianToJalali = function (g_y, g_m, g_d) {
            var self = this;
            var gy = parseInt(String(g_y), 10) - 1600;
            var gm = parseInt(String(g_m), 10) - 1;
            var gd = parseInt(String(g_d), 10) - 1;
            var g_day_no = 365 * gy +
                Math.floor((gy + 3) / 4) -
                Math.floor((gy + 99) / 100) +
                Math.floor((gy + 399) / 400);
            for (var i = 0; i < gm; ++i)
                g_day_no += self.g_days_in_month[i];
            if (gm > 1 && ((gy % 4 == 0 && gy % 100 != 0) || gy % 400 == 0))
                /* leap and after Feb */
                ++g_day_no;
            g_day_no += gd;
            var j_day_no = g_day_no - 79;
            var j_np = Math.floor(j_day_no / 12053);
            j_day_no %= 12053;
            var jy = 979 + 33 * j_np + 4 * Math.floor(j_day_no / 1461);
            j_day_no %= 1461;
            if (j_day_no >= 366) {
                jy += Math.floor((j_day_no - 1) / 365);
                j_day_no = (j_day_no - 1) % 365;
            }
            for (var i = 0; i < 11 && j_day_no >= self.j_days_in_month[i]; ++i) {
                j_day_no -= self.j_days_in_month[i];
            }
            var jm = i + 1;
            var jd = j_day_no + 1;
            return [jy, jm, jd];
        };
        Jalalidate.prototype.setJalali = function () {
            var self = this;
            self.jalalidate = self.gregorianToJalali(self.gregoriandate.getFullYear(), self.gregoriandate.getMonth() + 1, self.gregoriandate.getDate());
            self.jalalidate[1]--;
        };
        Jalalidate.prototype.getDate = function () {
            return this.jalalidate[2];
        };
        Jalalidate.prototype.getDay = function () {
            return this.gregoriandate.getDay();
        };
        Jalalidate.prototype.getFullYear = function () {
            return this.jalalidate[0];
        };
        Jalalidate.prototype.getHours = function () {
            return this.gregoriandate.getHours();
        };
        Jalalidate.prototype.getMilliseconds = function () {
            return this.gregoriandate.getMilliseconds();
        };
        Jalalidate.prototype.getMinutes = function () {
            return this.gregoriandate.getMinutes();
        };
        Jalalidate.prototype.getMonth = function () {
            return this.jalalidate[1];
        };
        Jalalidate.prototype.getSeconds = function () {
            return this.gregoriandate.getSeconds();
        };
        Jalalidate.prototype.getTime = function () {
            return this.gregoriandate.getTime();
        };
        Jalalidate.prototype.getTimezoneOffset = function () {
            return this.gregoriandate.getTimezoneOffset();
        };
        Jalalidate.prototype.getUTCDate = function () {
            return this.gregoriandate.getUTCDate();
        };
        Jalalidate.prototype.getUTCDay = function () {
            return this.gregoriandate.getUTCDay();
        };
        Jalalidate.prototype.getUTCFullYear = function () {
            return this.gregoriandate.getUTCFullYear();
        };
        Jalalidate.prototype.getUTCHours = function () {
            return this.gregoriandate.getUTCHours();
        };
        Jalalidate.prototype.getUTCMilliseconds = function () {
            return this.gregoriandate.getUTCMilliseconds();
        };
        Jalalidate.prototype.getUTCMinutes = function () {
            return this.gregoriandate.getUTCMinutes();
        };
        Jalalidate.prototype.getUTCMonth = function () {
            return this.gregoriandate.getUTCMonth();
        };
        Jalalidate.prototype.getUTCSeconds = function () {
            return this.gregoriandate.getUTCSeconds();
        };
        Jalalidate.prototype.getYear = function () {
            return this.gregoriandate.getFullYear() - 1900;
        };
        Jalalidate.prototype.setDate = function (day) {
            var self = this;
            var diff = -1 * (self.jalalidate[2] - day);
            var g = self.gregoriandate.setDate(self.gregoriandate.getDate() + diff);
            this.setJalali();
            return g;
        };
        Jalalidate.prototype.setFullYear = function (year, month, date) {
            var self = this;
            var m = 0;
            var d = 1;
            if (self.jalalidate !== undefined) {
                m = self.jalalidate[1];
                d = self.jalalidate[2];
            }
            if (month !== undefined)
                m = month;
            var negativeMonth = m < 0;
            if (negativeMonth)
                m = 0;
            else if (m == 12) {
                year++;
                m = 0;
            }
            if (date !== undefined)
                d = date;
            var negativeDate = d < 1;
            if (negativeDate)
                d = 1;
            var gDate = self.jalaliToGregorian(year, m + 1, d);
            var retval = self.gregoriandate.setFullYear(gDate[0], gDate[1] - 1, gDate[2]);
            if (negativeMonth || negativeDate) {
                if (negativeMonth)
                    retval = self.gregoriandate.setMonth(self.gregoriandate.getMonth() + month);
                if (negativeDate)
                    retval = self.gregoriandate.setDate(self.gregoriandate.getDate() + date - 1);
                this.setJalali();
            }
            else
                self.jalalidate = [year, m, d];
            return retval;
        };
        Jalalidate.prototype.setHours = function (hour, min, sec, millisec) {
            var self = this;
            var retval;
            if (min == undefined)
                retval = self.gregoriandate.setHours(hour);
            else if (sec == undefined)
                retval = self.gregoriandate.setHours(hour, min);
            else if (millisec == undefined)
                retval = self.gregoriandate.setHours(hour, min, sec);
            else
                retval = self.gregoriandate.setHours(hour, min, sec, millisec);
            this.setJalali();
            return retval;
        };
        Jalalidate.prototype.setMilliseconds = function (m) {
            var retval = this.gregoriandate.setMilliseconds(m);
            this.setJalali();
            return retval;
        };
        Jalalidate.prototype.setMinutes = function (m) {
            var retval = this.gregoriandate.setMinutes(m);
            this.setJalali();
            return retval;
        };
        Jalalidate.prototype.setMonth = function (month, date) {
            var self = this;
            var y = self.jalalidate[0];
            var m = parseInt(String(month), 10);
            var d = self.jalalidate[2];
            if (date !== undefined) {
                var dTemp = parseInt(String(date), 10);
                if (!isNaN(dTemp))
                    d = dTemp;
            }
            return this.setFullYear(y, m, d);
        };
        Jalalidate.prototype.setSeconds = function (s, m) {
            var retval = m != undefined
                ? this.gregoriandate.setSeconds(s, m)
                : this.gregoriandate.setSeconds(s);
            this.setJalali();
            return retval;
        };
        Jalalidate.prototype.setTime = function (m) {
            var retval = this.gregoriandate.setTime(m);
            this.setJalali();
            return retval;
        };
        Jalalidate.prototype.setUTCDate = function (d) {
            return this.gregoriandate.setUTCDate(d);
        };
        Jalalidate.prototype.setUTCFullYear = function (y, m, d) {
            return this.gregoriandate.setUTCFullYear(y, m, d);
        };
        Jalalidate.prototype.setUTCHours = function (h, m, s, mi) {
            return this.gregoriandate.setUTCHours(h, m, s, mi);
        };
        Jalalidate.prototype.setUTCMilliseconds = function (m) {
            return this.gregoriandate.setUTCMilliseconds(m);
        };
        Jalalidate.prototype.setUTCMinutes = function (m, s, mi) {
            return this.gregoriandate.setUTCMinutes(m, s, mi);
        };
        Jalalidate.prototype.setUTCMonth = function (m, d) {
            return this.gregoriandate.setUTCMonth(m, d);
        };
        Jalalidate.prototype.setUTCSeconds = function (s, m) {
            return this.gregoriandate.setUTCSeconds(s, m);
        };
        Jalalidate.prototype.toDateString = function () {
            var self = this;
            return (self.jalalidate[0] + "/" + self.jalalidate[1] + "/" + self.jalalidate[2]);
        };
        Jalalidate.prototype.toISOString = function () {
            return this.gregoriandate.toISOString();
        };
        Jalalidate.prototype.toJSON = function () {
            return this.toDateString();
        };
        Jalalidate.prototype.toLocaleDateString = function () {
            return this.toDateString();
        };
        Jalalidate.prototype.toLocaleTimeString = function () {
            return this.gregoriandate.toLocaleTimeString();
        };
        Jalalidate.prototype.toLocaleString = function () {
            return this.toDateString() + " " + this.toLocaleTimeString();
        };
        Jalalidate.prototype.toString = function () {
            return this.toLocaleString();
        };
        Jalalidate.prototype.toTimeString = function () {
            return this.toLocaleTimeString();
        };
        Jalalidate.prototype.toUTCString = function () {
            return this.gregoriandate.toUTCString();
        };
        Jalalidate.prototype.valueOf = function () {
            return this.gregoriandate.valueOf();
        };
        Jalalidate.UTC = function (y, m, d, h, mi, s, ml) {
            return Date.UTC(y, m, d, h, mi, s, ml);
        };
        Jalalidate.parse = function (datestring) {
            try {
                if (datestring.indexOf("Date(") > -1) {
                    var date = new Date(parseInt(datestring.replace(/^\/Date\((.*?)\)\/$/, "$1"), 10));
                    var y = new Jalalidate(date).getFullYear(), m = new Jalalidate(date).getMonth(), d = new Jalalidate(date).getDate();
                    return new Jalalidate(y, m, d).getTime();
                }
                else {
                    var y = parseInt(datestring.substring(0, 4)), m = parseInt(datestring.substring(5, 7)), d = parseInt(datestring.substring(8, 10));
                    return new Jalalidate(y, m - 1, d).getTime();
                }
            }
            catch (e) {
                return new Jalalidate(1300, 1, 1).getTime();
            }
        };
        return Jalalidate;
    }(Date));

    var fp = typeof window !== "undefined" && window.flatpickr !== undefined
        ? window.flatpickr
        : {
            l10ns: {},
        };
    function getWeek(givenDate) {
        var date = new Jalalidate(givenDate.getTime());
        date.setHours(0, 0, 0, 0);
        var week1 = new Jalalidate(givenDate.getFullYear(), 0, 1);
        var week2 = new Jalalidate(givenDate.getFullYear(), 0, (week1.getDay() + 6) % 7, 0, 0, 0);
        var weeks = 1 + Math.round((date.getTime() - week2.getTime()) / 86400000 / 7);
        if (weeks > 0)
            return weeks;
        return getWeek(new Jalalidate(givenDate.getFullYear(), 0, 0));
    }
    var Persian = {
        weekdays: {
            shorthand: ["ی", "د", "س", "چ", "پ", "ج", "ش"],
            longhand: [
                "یک‌شنبه",
                "دوشنبه",
                "سه‌شنبه",
                "چهارشنبه",
                "پنچ‌شنبه",
                "جمعه",
                "شنبه",
            ],
        },
        months: {
            shorthand: [
                "فروردین",
                "اردیبهشت",
                "خرداد",
                "تیر",
                "مرداد",
                "شهریور",
                "مهر",
                "آبان",
                "آذر",
                "دی",
                "بهمن",
                "اسفند",
            ],
            longhand: [
                "فروردین",
                "اردیبهشت",
                "خرداد",
                "تیر",
                "مرداد",
                "شهریور",
                "مهر",
                "آبان",
                "آذر",
                "دی",
                "بهمن",
                "اسفند",
            ],
        },
        daysInMonth: [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29],
        isLeap: function (month, year) {
            return (month === 11 && [1, 5, 9, 13, 17, 22, 26, 30].indexOf(year % 33) > -1);
        },
        firstDayOfWeek: 6,
        ordinal: function () {
            return "";
        },
        rangeSeparator: " تا ",
        weekAbbreviation: "هفته",
        scrollTitle: "اسکرول نمایید",
        toggleTitle: "برای تغییر کلیک نمایید",
        amPM: ["صبح", "عصر"],
        yearAriaLabel: "سال",
        monthAriaLabel: "ماه",
        hourAriaLabel: "ساعت",
        minuteAriaLabel: "دقیقه",
        time_24hr: false,
        getWeek: getWeek,
        date: Jalalidate,
    };
    fp.l10ns.fa = Persian;
    var fa = fp.l10ns;

    exports.Persian = Persian;
    exports["default"] = fa;

    Object.defineProperty(exports, '__esModule', { value: true });

}));
