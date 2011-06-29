#!/usr/bin/python
"""
Module used to parse the autotest job results and generate an HTML report.

@copyright: (c)2005-2007 Matt Kruse (javascripttoolbox.com)
@copyright: Red Hat 2008-2009
@author: Dror Russo (drusso@redhat.com)
"""

import os, sys, re, getopt, time, datetime, commands
import common


format_css = """
html,body {
    padding:0;
    color:#222;
    background:#FFFFFF;
}

body {
    padding:0px;
    font:76%/150% "Lucida Grande", "Lucida Sans Unicode", Lucida, Verdana, Geneva, Arial, Helvetica, sans-serif;
}

#page_title{
    text-decoration:none;
    font:bold 2em/2em Arial, Helvetica, sans-serif;
    text-transform:none;
    text-align: left;
    color:#555555;
    border-bottom: 1px solid #555555;
}

#page_sub_title{
        text-decoration:none;
        font:bold 16px Arial, Helvetica, sans-serif;
        text-transform:uppercase;
        text-align: left;
        color:#555555;
    margin-bottom:0;
}

#comment{
        text-decoration:none;
        font:bold 10px Arial, Helvetica, sans-serif;
        text-transform:none;
        text-align: left;
        color:#999999;
    margin-top:0;
}


#meta_headline{
                text-decoration:none;
                font-family: Verdana, Geneva, Arial, Helvetica, sans-serif ;
                text-align: left;
                color:black;
                font-weight: bold;
                font-size: 14px;
        }


table.meta_table
{text-align: center;
font-family: Verdana, Geneva, Arial, Helvetica, sans-serif ;
width: 90%;
background-color: #FFFFFF;
border: 0px;
border-top: 1px #003377 solid;
border-bottom: 1px #003377 solid;
border-right: 1px #003377 solid;
border-left: 1px #003377 solid;
border-collapse: collapse;
border-spacing: 0px;}

table.meta_table td
{background-color: #FFFFFF;
color: #000;
padding: 4px;
border-top: 1px #BBBBBB solid;
border-bottom: 1px #BBBBBB solid;
font-weight: normal;
font-size: 13px;}


table.stats
{text-align: center;
font-family: Verdana, Geneva, Arial, Helvetica, sans-serif ;
width: 100%;
background-color: #FFFFFF;
border: 0px;
border-top: 1px #003377 solid;
border-bottom: 1px #003377 solid;
border-right: 1px #003377 solid;
border-left: 1px #003377 solid;
border-collapse: collapse;
border-spacing: 0px;}

table.stats td{
background-color: #FFFFFF;
color: #000;
padding: 4px;
border-top: 1px #BBBBBB solid;
border-bottom: 1px #BBBBBB solid;
font-weight: normal;
font-size: 11px;}

table.stats th{
background: #dcdcdc;
color: #000;
padding: 6px;
font-size: 12px;
border-bottom: 1px #003377 solid;
font-weight: bold;}

table.stats td.top{
background-color: #dcdcdc;
color: #000;
padding: 6px;
text-align: center;
border: 0px;
border-bottom: 1px #003377 solid;
font-size: 10px;
font-weight: bold;}

table.stats th.table-sorted-asc{
        background-image: url(ascending.gif);
        background-position: top left  ;
        background-repeat: no-repeat;
}

table.stats th.table-sorted-desc{
        background-image: url(descending.gif);
        background-position: top left;
        background-repeat: no-repeat;
}

table.stats2
{text-align: left;
font-family: Verdana, Geneva, Arial, Helvetica, sans-serif ;
width: 100%;
background-color: #FFFFFF;
border: 0px;
}

table.stats2 td{
background-color: #FFFFFF;
color: #000;
padding: 0px;
font-weight: bold;
font-size: 13px;}



/* Put this inside a @media qualifier so Netscape 4 ignores it */
@media screen, print {
        /* Turn off list bullets */
        ul.mktree  li { list-style: none; }
        /* Control how "spaced out" the tree is */
        ul.mktree, ul.mktree ul , ul.mktree li { margin-left:10px; padding:0px; }
        /* Provide space for our own "bullet" inside the LI */
        ul.mktree  li           .bullet { padding-left: 15px; }
        /* Show "bullets" in the links, depending on the class of the LI that the link's in */
        ul.mktree  li.liOpen    .bullet { cursor: pointer; }
        ul.mktree  li.liClosed  .bullet { cursor: pointer;  }
        ul.mktree  li.liBullet  .bullet { cursor: default; }
        /* Sublists are visible or not based on class of parent LI */
        ul.mktree  li.liOpen    ul { display: block; }
        ul.mktree  li.liClosed  ul { display: none; }

        /* Format menu items differently depending on what level of the tree they are in */
        /* Uncomment this if you want your fonts to decrease in size the deeper they are in the tree */
/*
        ul.mktree  li ul li { font-size: 90% }
*/
}
"""


table_js = """
/**
 * Copyright (c)2005-2007 Matt Kruse (javascripttoolbox.com)
 *
 * Dual licensed under the MIT and GPL licenses.
 * This basically means you can use this code however you want for
 * free, but don't claim to have written it yourself!
 * Donations always accepted: http://www.JavascriptToolbox.com/donate/
 *
 * Please do not link to the .js files on javascripttoolbox.com from
 * your site. Copy the files locally to your server instead.
 *
 */
/**
 * Table.js
 * Functions for interactive Tables
 *
 * Copyright (c) 2007 Matt Kruse (javascripttoolbox.com)
 * Dual licensed under the MIT and GPL licenses.
 *
 * @version 0.981
 *
 * @history 0.981 2007-03-19 Added Sort.numeric_comma, additional date parsing formats
 * @history 0.980 2007-03-18 Release new BETA release pending some testing. Todo: Additional docs, examples, plus jQuery plugin.
 * @history 0.959 2007-03-05 Added more "auto" functionality, couple bug fixes
 * @history 0.958 2007-02-28 Added auto functionality based on class names
 * @history 0.957 2007-02-21 Speed increases, more code cleanup, added Auto Sort functionality
 * @history 0.956 2007-02-16 Cleaned up the code and added Auto Filter functionality.
 * @history 0.950 2006-11-15 First BETA release.
 *
 * @todo Add more date format parsers
 * @todo Add style classes to colgroup tags after sorting/filtering in case the user wants to highlight the whole column
 * @todo Correct for colspans in data rows (this may slow it down)
 * @todo Fix for IE losing form control values after sort?
 */

/**
 * Sort Functions
 */
var Sort = (function(){
        var sort = {};
        // Default alpha-numeric sort
        // --------------------------
        sort.alphanumeric = function(a,b) {
                return (a==b)?0:(a<b)?-1:1;
        };
        sort.alphanumeric_rev = function(a,b) {
                return (a==b)?0:(a<b)?1:-1;
        };
        sort['default'] = sort.alphanumeric; // IE chokes on sort.default

        // This conversion is generalized to work for either a decimal separator of , or .
        sort.numeric_converter = function(separator) {
                return function(val) {
                        if (typeof(val)=="string") {
                                val = parseFloat(val.replace(/^[^\d\.]*([\d., ]+).*/g,"$1").replace(new RegExp("[^\\\d"+separator+"]","g"),'').replace(/,/,'.')) || 0;
                        }
                        return val || 0;
                };
        };

        // Numeric Reversed Sort
        // ------------
        sort.numeric_rev = function(a,b) {
                if (sort.numeric.convert(a)>sort.numeric.convert(b)) {
                        return (-1);
                }
                if (sort.numeric.convert(a)==sort.numeric.convert(b)) {
                        return 0;
                }
                if (sort.numeric.convert(a)<sort.numeric.convert(b)) {
                        return 1;
                }
        };


        // Numeric Sort
        // ------------
        sort.numeric = function(a,b) {
                return sort.numeric.convert(a)-sort.numeric.convert(b);
        };
        sort.numeric.convert = sort.numeric_converter(".");

        // Numeric Sort - comma decimal separator
        // --------------------------------------
        sort.numeric_comma = function(a,b) {
                return sort.numeric_comma.convert(a)-sort.numeric_comma.convert(b);
        };
        sort.numeric_comma.convert = sort.numeric_converter(",");

        // Case-insensitive Sort
        // ---------------------
        sort.ignorecase = function(a,b) {
                return sort.alphanumeric(sort.ignorecase.convert(a),sort.ignorecase.convert(b));
        };
        sort.ignorecase.convert = function(val) {
                if (val==null) { return ""; }
                return (""+val).toLowerCase();
        };

        // Currency Sort
        // -------------
        sort.currency = sort.numeric; // Just treat it as numeric!
        sort.currency_comma = sort.numeric_comma;

        // Date sort
        // ---------
        sort.date = function(a,b) {
                return sort.numeric(sort.date.convert(a),sort.date.convert(b));
        };
        // Convert 2-digit years to 4
        sort.date.fixYear=function(yr) {
                yr = +yr;
                if (yr<50) { yr += 2000; }
                else if (yr<100) { yr += 1900; }
                return yr;
        };
        sort.date.formats = [
                // YY[YY]-MM-DD
                { re:/(\d{2,4})-(\d{1,2})-(\d{1,2})/ , f:function(x){ return (new Date(sort.date.fixYear(x[1]),+x[2],+x[3])).getTime(); } }
                // MM/DD/YY[YY] or MM-DD-YY[YY]
                ,{ re:/(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})/ , f:function(x){ return (new Date(sort.date.fixYear(x[3]),+x[1],+x[2])).getTime(); } }
                // Any catch-all format that new Date() can handle. This is not reliable except for long formats, for example: 31 Jan 2000 01:23:45 GMT
                ,{ re:/(.*\d{4}.*\d+:\d+\d+.*)/, f:function(x){ var d=new Date(x[1]); if(d){return d.getTime();} } }
        ];
        sort.date.convert = function(val) {
                var m,v, f = sort.date.formats;
                for (var i=0,L=f.length; i<L; i++) {
                        if (m=val.match(f[i].re)) {
                                v=f[i].f(m);
                                if (typeof(v)!="undefined") { return v; }
                        }
                }
                return 9999999999999; // So non-parsed dates will be last, not first
        };

        return sort;
})();

/**
 * The main Table namespace
 */
var Table = (function(){

        /**
         * Determine if a reference is defined
         */
        function def(o) {return (typeof o!="undefined");};

        /**
         * Determine if an object or class string contains a given class.
         */
        function hasClass(o,name) {
                return new RegExp("(^|\\\s)"+name+"(\\\s|$)").test(o.className);
        };

        /**
         * Add a class to an object
         */
        function addClass(o,name) {
                var c = o.className || "";
                if (def(c) && !hasClass(o,name)) {
                        o.className += (c?" ":"") + name;
                }
        };

        /**
         * Remove a class from an object
         */
        function removeClass(o,name) {
                var c = o.className || "";
                o.className = c.replace(new RegExp("(^|\\\s)"+name+"(\\\s|$)"),"$1");
        };

        /**
         * For classes that match a given substring, return the rest
         */
        function classValue(o,prefix) {
                var c = o.className;
                if (c.match(new RegExp("(^|\\\s)"+prefix+"([^ ]+)"))) {
                        return RegExp.$2;
                }
                return null;
        };

        /**
         * Return true if an object is hidden.
         * This uses the "russian doll" technique to unwrap itself to the most efficient
         * function after the first pass. This avoids repeated feature detection that
         * would always fall into the same block of code.
         */
         function isHidden(o) {
                if (window.getComputedStyle) {
                        var cs = window.getComputedStyle;
                        return (isHidden = function(o) {
                                return 'none'==cs(o,null).getPropertyValue('display');
                        })(o);
                }
                else if (window.currentStyle) {
                        return(isHidden = function(o) {
                                return 'none'==o.currentStyle['display'];
                        })(o);
                }
                return (isHidden = function(o) {
                        return 'none'==o.style['display'];
                })(o);
        };

        /**
         * Get a parent element by tag name, or the original element if it is of the tag type
         */
        function getParent(o,a,b) {
                if (o!=null && o.nodeName) {
                        if (o.nodeName==a || (b && o.nodeName==b)) {
                                return o;
                        }
                        while (o=o.parentNode) {
                                if (o.nodeName && (o.nodeName==a || (b && o.nodeName==b))) {
                                        return o;
                                }
                        }
                }
                return null;
        };

        /**
         * Utility function to copy properties from one object to another
         */
        function copy(o1,o2) {
                for (var i=2;i<arguments.length; i++) {
                        var a = arguments[i];
                        if (def(o1[a])) {
                                o2[a] = o1[a];
                        }
                }
        }

        // The table object itself
        var table = {
                //Class names used in the code
                AutoStripeClassName:"table-autostripe",
                StripeClassNamePrefix:"table-stripeclass:",

                AutoSortClassName:"table-autosort",
                AutoSortColumnPrefix:"table-autosort:",
                AutoSortTitle:"Click to sort",
                SortedAscendingClassName:"table-sorted-asc",
                SortedDescendingClassName:"table-sorted-desc",
                SortableClassName:"table-sortable",
                SortableColumnPrefix:"table-sortable:",
                NoSortClassName:"table-nosort",

                AutoFilterClassName:"table-autofilter",
                FilteredClassName:"table-filtered",
                FilterableClassName:"table-filterable",
                FilteredRowcountPrefix:"table-filtered-rowcount:",
                RowcountPrefix:"table-rowcount:",
                FilterAllLabel:"Filter: All",

                AutoPageSizePrefix:"table-autopage:",
                AutoPageJumpPrefix:"table-page:",
                PageNumberPrefix:"table-page-number:",
                PageCountPrefix:"table-page-count:"
        };

        /**
         * A place to store misc table information, rather than in the table objects themselves
         */
        table.tabledata = {};

        /**
         * Resolve a table given an element reference, and make sure it has a unique ID
         */
        table.uniqueId=1;
        table.resolve = function(o,args) {
                if (o!=null && o.nodeName && o.nodeName!="TABLE") {
                        o = getParent(o,"TABLE");
                }
                if (o==null) { return null; }
                if (!o.id) {
                        var id = null;
                        do { var id = "TABLE_"+(table.uniqueId++); }
                                while (document.getElementById(id)!=null);
                        o.id = id;
                }
                this.tabledata[o.id] = this.tabledata[o.id] || {};
                if (args) {
                        copy(args,this.tabledata[o.id],"stripeclass","ignorehiddenrows","useinnertext","sorttype","col","desc","page","pagesize");
                }
                return o;
        };


        /**
         * Run a function against each cell in a table header or footer, usually
         * to add or remove css classes based on sorting, filtering, etc.
         */
        table.processTableCells = function(t, type, func, arg) {
                t = this.resolve(t);
                if (t==null) { return; }
                if (type!="TFOOT") {
                        this.processCells(t.tHead, func, arg);
                }
                if (type!="THEAD") {
                        this.processCells(t.tFoot, func, arg);
                }
        };

        /**
         * Internal method used to process an arbitrary collection of cells.
         * Referenced by processTableCells.
         * It's done this way to avoid getElementsByTagName() which would also return nested table cells.
         */
        table.processCells = function(section,func,arg) {
                if (section!=null) {
                        if (section.rows && section.rows.length && section.rows.length>0) {
                                var rows = section.rows;
                                for (var j=0,L2=rows.length; j<L2; j++) {
                                        var row = rows[j];
                                        if (row.cells && row.cells.length && row.cells.length>0) {
                                                var cells = row.cells;
                                                for (var k=0,L3=cells.length; k<L3; k++) {
                                                        var cellsK = cells[k];
                                                        func.call(this,cellsK,arg);
                                                }
                                        }
                                }
                        }
                }
        };

        /**
         * Get the cellIndex value for a cell. This is only needed because of a Safari
         * bug that causes cellIndex to exist but always be 0.
         * Rather than feature-detecting each time it is called, the function will
         * re-write itself the first time it is called.
         */
        table.getCellIndex = function(td) {
                var tr = td.parentNode;
                var cells = tr.cells;
                if (cells && cells.length) {
                        if (cells.length>1 && cells[cells.length-1].cellIndex>0) {
                                // Define the new function, overwrite the one we're running now, and then run the new one
                                (this.getCellIndex = function(td) {
                                        return td.cellIndex;
                                })(td);
                        }
                        // Safari will always go through this slower block every time. Oh well.
                        for (var i=0,L=cells.length; i<L; i++) {
                                if (tr.cells[i]==td) {
                                        return i;
                                }
                        }
                }
                return 0;
        };

        /**
         * A map of node names and how to convert them into their "value" for sorting, filtering, etc.
         * These are put here so it is extensible.
         */
        table.nodeValue = {
                'INPUT':function(node) {
                        if (def(node.value) && node.type && ((node.type!="checkbox" && node.type!="radio") || node.checked)) {
                                return node.value;
                        }
                        return "";
                },
                'SELECT':function(node) {
                        if (node.selectedIndex>=0 && node.options) {
                                // Sort select elements by the visible text
                                return node.options[node.selectedIndex].text;
                        }
                        return "";
                },
                'IMG':function(node) {
                        return node.name || "";
                }
        };

        /**
         * Get the text value of a cell. Only use innerText if explicitly told to, because
         * otherwise we want to be able to handle sorting on inputs and other types
         */
        table.getCellValue = function(td,useInnerText) {
                if (useInnerText && def(td.innerText)) {
                        return td.innerText;
                }
                if (!td.childNodes) {
                        return "";
                }
                var childNodes=td.childNodes;
                var ret = "";
                for (var i=0,L=childNodes.length; i<L; i++) {
                        var node = childNodes[i];
                        var type = node.nodeType;
                        // In order to get realistic sort results, we need to treat some elements in a special way.
                        // These behaviors are defined in the nodeValue() object, keyed by node name
                        if (type==1) {
                                var nname = node.nodeName;
                                if (this.nodeValue[nname]) {
                                        ret += this.nodeValue[nname](node);
                                }
                                else {
                                        ret += this.getCellValue(node);
                                }
                        }
                        else if (type==3) {
                                if (def(node.innerText)) {
                                        ret += node.innerText;
                                }
                                else if (def(node.nodeValue)) {
                                        ret += node.nodeValue;
                                }
                        }
                }
                return ret;
        };

        /**
         * Consider colspan and rowspan values in table header cells to calculate the actual cellIndex
         * of a given cell. This is necessary because if the first cell in row 0 has a rowspan of 2,
         * then the first cell in row 1 will have a cellIndex of 0 rather than 1, even though it really
         * starts in the second column rather than the first.
         * See: http://www.javascripttoolbox.com/temp/table_cellindex.html
         */
        table.tableHeaderIndexes = {};
        table.getActualCellIndex = function(tableCellObj) {
                if (!def(tableCellObj.cellIndex)) { return null; }
                var tableObj = getParent(tableCellObj,"TABLE");
                var cellCoordinates = tableCellObj.parentNode.rowIndex+"-"+this.getCellIndex(tableCellObj);

                // If it has already been computed, return the answer from the lookup table
                if (def(this.tableHeaderIndexes[tableObj.id])) {
                        return this.tableHeaderIndexes[tableObj.id][cellCoordinates];
                }

                var matrix = [];
                this.tableHeaderIndexes[tableObj.id] = {};
                var thead = getParent(tableCellObj,"THEAD");
                var trs = thead.getElementsByTagName('TR');

                // Loop thru every tr and every cell in the tr, building up a 2-d array "grid" that gets
                // populated with an "x" for each space that a cell takes up. If the first cell is colspan
                // 2, it will fill in values [0] and [1] in the first array, so that the second cell will
                // find the first empty cell in the first row (which will be [2]) and know that this is
                // where it sits, rather than its internal .cellIndex value of [1].
                for (var i=0; i<trs.length; i++) {
                        var cells = trs[i].cells;
                        for (var j=0; j<cells.length; j++) {
                                var c = cells[j];
                                var rowIndex = c.parentNode.rowIndex;
                                var cellId = rowIndex+"-"+this.getCellIndex(c);
                                var rowSpan = c.rowSpan || 1;
                                var colSpan = c.colSpan || 1;
                                var firstAvailCol;
                                if(!def(matrix[rowIndex])) {
                                        matrix[rowIndex] = [];
                                }
                                var m = matrix[rowIndex];
                                // Find first available column in the first row
                                for (var k=0; k<m.length+1; k++) {
                                        if (!def(m[k])) {
                                                firstAvailCol = k;
                                                break;
                                        }
                                }
                                this.tableHeaderIndexes[tableObj.id][cellId] = firstAvailCol;
                                for (var k=rowIndex; k<rowIndex+rowSpan; k++) {
                                        if(!def(matrix[k])) {
                                                matrix[k] = [];
                                        }
                                        var matrixrow = matrix[k];
                                        for (var l=firstAvailCol; l<firstAvailCol+colSpan; l++) {
                                                matrixrow[l] = "x";
                                        }
                                }
                        }
                }
                // Store the map so future lookups are fast.
                return this.tableHeaderIndexes[tableObj.id][cellCoordinates];
        };

        /**
         * Sort all rows in each TBODY (tbodies are sorted independent of each other)
         */
        table.sort = function(o,args) {
                var t, tdata, sortconvert=null;
                // Allow for a simple passing of sort type as second parameter
                if (typeof(args)=="function") {
                        args={sorttype:args};
                }
                args = args || {};

                // If no col is specified, deduce it from the object sent in
                if (!def(args.col)) {
                        args.col = this.getActualCellIndex(o) || 0;
                }
                // If no sort type is specified, default to the default sort
                args.sorttype = args.sorttype || Sort['default'];

                // Resolve the table
                t = this.resolve(o,args);
                tdata = this.tabledata[t.id];

                // If we are sorting on the same column as last time, flip the sort direction
                if (def(tdata.lastcol) && tdata.lastcol==tdata.col && def(tdata.lastdesc)) {
                        tdata.desc = !tdata.lastdesc;
                }
                else {
                        tdata.desc = !!args.desc;
                }

                // Store the last sorted column so clicking again will reverse the sort order
                tdata.lastcol=tdata.col;
                tdata.lastdesc=!!tdata.desc;

                // If a sort conversion function exists, pre-convert cell values and then use a plain alphanumeric sort
                var sorttype = tdata.sorttype;
                if (typeof(sorttype.convert)=="function") {
                        sortconvert=tdata.sorttype.convert;
                        sorttype=Sort.alphanumeric;
                }

                // Loop through all THEADs and remove sorted class names, then re-add them for the col
                // that is being sorted
                this.processTableCells(t,"THEAD",
                        function(cell) {
                                if (hasClass(cell,this.SortableClassName)) {
                                        removeClass(cell,this.SortedAscendingClassName);
                                        removeClass(cell,this.SortedDescendingClassName);
                                        // If the computed colIndex of the cell equals the sorted colIndex, flag it as sorted
                                        if (tdata.col==table.getActualCellIndex(cell) && (classValue(cell,table.SortableClassName))) {
                                                addClass(cell,tdata.desc?this.SortedAscendingClassName:this.SortedDescendingClassName);
                                        }
                                }
                        }
                );

                // Sort each tbody independently
                var bodies = t.tBodies;
                if (bodies==null || bodies.length==0) { return; }

                // Define a new sort function to be called to consider descending or not
                var newSortFunc = (tdata.desc)?
                        function(a,b){return sorttype(b[0],a[0]);}
                        :function(a,b){return sorttype(a[0],b[0]);};

                var useinnertext=!!tdata.useinnertext;
                var col = tdata.col;

                for (var i=0,L=bodies.length; i<L; i++) {
                        var tb = bodies[i], tbrows = tb.rows, rows = [];

                        // Allow tbodies to request that they not be sorted
                        if(!hasClass(tb,table.NoSortClassName)) {
                                // Create a separate array which will store the converted values and refs to the
                                // actual rows. This is the array that will be sorted.
                                var cRow, cRowIndex=0;
                                if (cRow=tbrows[cRowIndex]){
                                        // Funky loop style because it's considerably faster in IE
                                        do {
                                                if (rowCells = cRow.cells) {
                                                        var cellValue = (col<rowCells.length)?this.getCellValue(rowCells[col],useinnertext):null;
                                                        if (sortconvert) cellValue = sortconvert(cellValue);
                                                        rows[cRowIndex] = [cellValue,tbrows[cRowIndex]];
                                                }
                                        } while (cRow=tbrows[++cRowIndex])
                                }

                                // Do the actual sorting
                                rows.sort(newSortFunc);

                                // Move the rows to the correctly sorted order. Appending an existing DOM object just moves it!
                                cRowIndex=0;
                                var displayedCount=0;
                                var f=[removeClass,addClass];
                                if (cRow=rows[cRowIndex]){
                                        do {
                                                tb.appendChild(cRow[1]);
                                        } while (cRow=rows[++cRowIndex])
                                }
                        }
                }

                // If paging is enabled on the table, then we need to re-page because the order of rows has changed!
                if (tdata.pagesize) {
                        this.page(t); // This will internally do the striping
                }
                else {
                        // Re-stripe if a class name was supplied
                        if (tdata.stripeclass) {
                                this.stripe(t,tdata.stripeclass,!!tdata.ignorehiddenrows);
                        }
                }
        };

        /**
        * Apply a filter to rows in a table and hide those that do not match.
        */
        table.filter = function(o,filters,args) {
                var cell;
                args = args || {};

                var t = this.resolve(o,args);
                var tdata = this.tabledata[t.id];

                // If new filters were passed in, apply them to the table's list of filters
                if (!filters) {
                        // If a null or blank value was sent in for 'filters' then that means reset the table to no filters
                        tdata.filters = null;
                }
                else {
                        // Allow for passing a select list in as the filter, since this is common design
                        if (filters.nodeName=="SELECT" && filters.type=="select-one" && filters.selectedIndex>-1) {
                                filters={ 'filter':filters.options[filters.selectedIndex].value };
                        }
                        // Also allow for a regular input
                        if (filters.nodeName=="INPUT" && filters.type=="text") {
                                filters={ 'filter':"/"+filters.value+"/" };
                        }
                        // Force filters to be an array
                        if (typeof(filters)=="object" && !filters.length) {
                                filters = [filters];
                        }

                        // Convert regular expression strings to RegExp objects and function strings to function objects
                        for (var i=0,L=filters.length; i<L; i++) {
                                var filter = filters[i];
                                if (typeof(filter.filter)=="string") {
                                        // If a filter string is like "/expr/" then turn it into a Regex
                                        if (filter.filter.match(/^\/(.*)\/$/)) {
                                                filter.filter = new RegExp(RegExp.$1);
                                                filter.filter.regex=true;
                                        }
                                        // If filter string is like "function (x) { ... }" then turn it into a function
                                        else if (filter.filter.match(/^function\s*\(([^\)]*)\)\s*\{(.*)}\s*$/)) {
                                                filter.filter = Function(RegExp.$1,RegExp.$2);
                                        }
                                }
                                // If some non-table object was passed in rather than a 'col' value, resolve it
                                // and assign it's column index to the filter if it doesn't have one. This way,
                                // passing in a cell reference or a select object etc instead of a table object
                                // will automatically set the correct column to filter.
                                if (filter && !def(filter.col) && (cell=getParent(o,"TD","TH"))) {
                                        filter.col = this.getCellIndex(cell);
                                }

                                // Apply the passed-in filters to the existing list of filters for the table, removing those that have a filter of null or ""
                                if ((!filter || !filter.filter) && tdata.filters) {
                                        delete tdata.filters[filter.col];
                                }
                                else {
                                        tdata.filters = tdata.filters || {};
                                        tdata.filters[filter.col] = filter.filter;
                                }
                        }
                        // If no more filters are left, then make sure to empty out the filters object
                        for (var j in tdata.filters) { var keep = true; }
                        if (!keep) {
                                tdata.filters = null;
                        }
                }
                // Everything's been setup, so now scrape the table rows
                return table.scrape(o);
        };

        /**
         * "Page" a table by showing only a subset of the rows
         */
        table.page = function(t,page,args) {
                args = args || {};
                if (def(page)) { args.page = page; }
                return table.scrape(t,args);
        };

        /**
         * Jump forward or back any number of pages
         */
        table.pageJump = function(t,count,args) {
                t = this.resolve(t,args);
                return this.page(t,(table.tabledata[t.id].page||0)+count,args);
        };

        /**
         * Go to the next page of a paged table
         */
        table.pageNext = function(t,args) {
                return this.pageJump(t,1,args);
        };

        /**
         * Go to the previous page of a paged table
         */
        table.pagePrevious = function(t,args) {
                return this.pageJump(t,-1,args);
        };

        /**
        * Scrape a table to either hide or show each row based on filters and paging
        */
        table.scrape = function(o,args) {
                var col,cell,filterList,filterReset=false,filter;
                var page,pagesize,pagestart,pageend;
                var unfilteredrows=[],unfilteredrowcount=0,totalrows=0;
                var t,tdata,row,hideRow;
                args = args || {};

                // Resolve the table object
                t = this.resolve(o,args);
                tdata = this.tabledata[t.id];

                // Setup for Paging
                var page = tdata.page;
                if (def(page)) {
                        // Don't let the page go before the beginning
                        if (page<0) { tdata.page=page=0; }
                        pagesize = tdata.pagesize || 25; // 25=arbitrary default
                        pagestart = page*pagesize+1;
                        pageend = pagestart + pagesize - 1;
                }

                // Scrape each row of each tbody
                var bodies = t.tBodies;
                if (bodies==null || bodies.length==0) { return; }
                for (var i=0,L=bodies.length; i<L; i++) {
                        var tb = bodies[i];
                        for (var j=0,L2=tb.rows.length; j<L2; j++) {
                                row = tb.rows[j];
                                hideRow = false;

                                // Test if filters will hide the row
                                if (tdata.filters && row.cells) {
                                        var cells = row.cells;
                                        var cellsLength = cells.length;
                                        // Test each filter
                                        for (col in tdata.filters) {
                                                if (!hideRow) {
                                                        filter = tdata.filters[col];
                                                        if (filter && col<cellsLength) {
                                                                var val = this.getCellValue(cells[col]);
                                                                if (filter.regex && val.search) {
                                                                        hideRow=(val.search(filter)<0);
                                                                }
                                                                else if (typeof(filter)=="function") {
                                                                        hideRow=!filter(val,cells[col]);
                                                                }
                                                                else {
                                                                        hideRow = (val!=filter);
                                                                }
                                                        }
                                                }
                                        }
                                }

                                // Keep track of the total rows scanned and the total runs _not_ filtered out
                                totalrows++;
                                if (!hideRow) {
                                        unfilteredrowcount++;
                                        if (def(page)) {
                                                // Temporarily keep an array of unfiltered rows in case the page we're on goes past
                                                // the last page and we need to back up. Don't want to filter again!
                                                unfilteredrows.push(row);
                                                if (unfilteredrowcount<pagestart || unfilteredrowcount>pageend) {
                                                        hideRow = true;
                                                }
                                        }
                                }

                                row.style.display = hideRow?"none":"";
                        }
                }

                if (def(page)) {
                        // Check to see if filtering has put us past the requested page index. If it has,
                        // then go back to the last page and show it.
                        if (pagestart>=unfilteredrowcount) {
                                pagestart = unfilteredrowcount-(unfilteredrowcount%pagesize);
                                tdata.page = page = pagestart/pagesize;
                                for (var i=pagestart,L=unfilteredrows.length; i<L; i++) {
                                        unfilteredrows[i].style.display="";
                                }
                        }
                }

                // Loop through all THEADs and add/remove filtered class names
                this.processTableCells(t,"THEAD",
                        function(c) {
                                ((tdata.filters && def(tdata.filters[table.getCellIndex(c)]) && hasClass(c,table.FilterableClassName))?addClass:removeClass)(c,table.FilteredClassName);
                        }
                );

                // Stripe the table if necessary
                if (tdata.stripeclass) {
                        this.stripe(t);
                }

                // Calculate some values to be returned for info and updating purposes
                var pagecount = Math.floor(unfilteredrowcount/pagesize)+1;
                if (def(page)) {
                        // Update the page number/total containers if they exist
                        if (tdata.container_number) {
                                tdata.container_number.innerHTML = page+1;
                        }
                        if (tdata.container_count) {
                                tdata.container_count.innerHTML = pagecount;
                        }
                }

                // Update the row count containers if they exist
                if (tdata.container_filtered_count) {
                        tdata.container_filtered_count.innerHTML = unfilteredrowcount;
                }
                if (tdata.container_all_count) {
                        tdata.container_all_count.innerHTML = totalrows;
                }
                return { 'data':tdata, 'unfilteredcount':unfilteredrowcount, 'total':totalrows, 'pagecount':pagecount, 'page':page, 'pagesize':pagesize };
        };

        /**
         * Shade alternate rows, aka Stripe the table.
         */
        table.stripe = function(t,className,args) {
                args = args || {};
                args.stripeclass = className;

                t = this.resolve(t,args);
                var tdata = this.tabledata[t.id];

                var bodies = t.tBodies;
                if (bodies==null || bodies.length==0) {
                        return;
                }

                className = tdata.stripeclass;
                // Cache a shorter, quicker reference to either the remove or add class methods
                var f=[removeClass,addClass];
                for (var i=0,L=bodies.length; i<L; i++) {
                        var tb = bodies[i], tbrows = tb.rows, cRowIndex=0, cRow, displayedCount=0;
                        if (cRow=tbrows[cRowIndex]){
                                // The ignorehiddenrows test is pulled out of the loop for a slight speed increase.
                                // Makes a bigger difference in FF than in IE.
                                // In this case, speed always wins over brevity!
                                if (tdata.ignoreHiddenRows) {
                                        do {
                                                f[displayedCount++%2](cRow,className);
                                        } while (cRow=tbrows[++cRowIndex])
                                }
                                else {
                                        do {
                                                if (!isHidden(cRow)) {
                                                        f[displayedCount++%2](cRow,className);
                                                }
                                        } while (cRow=tbrows[++cRowIndex])
                                }
                        }
                }
        };

        /**
         * Build up a list of unique values in a table column
         */
        table.getUniqueColValues = function(t,col) {
                var values={}, bodies = this.resolve(t).tBodies;
                for (var i=0,L=bodies.length; i<L; i++) {
                        var tbody = bodies[i];
                        for (var r=0,L2=tbody.rows.length; r<L2; r++) {
                                values[this.getCellValue(tbody.rows[r].cells[col])] = true;
                        }
                }
                var valArray = [];
                for (var val in values) {
                        valArray.push(val);
                }
                return valArray.sort();
        };

        /**
         * Scan the document on load and add sorting, filtering, paging etc ability automatically
         * based on existence of class names on the table and cells.
         */
        table.auto = function(args) {
                var cells = [], tables = document.getElementsByTagName("TABLE");
                var val,tdata;
                if (tables!=null) {
                        for (var i=0,L=tables.length; i<L; i++) {
                                var t = table.resolve(tables[i]);
                                tdata = table.tabledata[t.id];
                                if (val=classValue(t,table.StripeClassNamePrefix)) {
                                        tdata.stripeclass=val;
                                }
                                // Do auto-filter if necessary
                                if (hasClass(t,table.AutoFilterClassName)) {
                                        table.autofilter(t);
                                }
                                // Do auto-page if necessary
                                if (val = classValue(t,table.AutoPageSizePrefix)) {
                                        table.autopage(t,{'pagesize':+val});
                                }
                                // Do auto-sort if necessary
                                if ((val = classValue(t,table.AutoSortColumnPrefix)) || (hasClass(t,table.AutoSortClassName))) {
                                        table.autosort(t,{'col':(val==null)?null:+val});
                                }
                                // Do auto-stripe if necessary
                                if (tdata.stripeclass && hasClass(t,table.AutoStripeClassName)) {
                                        table.stripe(t);
                                }
                        }
                }
        };

        /**
         * Add sorting functionality to a table header cell
         */
        table.autosort = function(t,args) {
                t = this.resolve(t,args);
                var tdata = this.tabledata[t.id];
                this.processTableCells(t, "THEAD", function(c) {
                        var type = classValue(c,table.SortableColumnPrefix);
                        if (type!=null) {
                                type = type || "default";
                                c.title =c.title || table.AutoSortTitle;
                                addClass(c,table.SortableClassName);
                                c.onclick = Function("","Table.sort(this,{'sorttype':Sort['"+type+"']})");
                                // If we are going to auto sort on a column, we need to keep track of what kind of sort it will be
                                if (args.col!=null) {
                                        if (args.col==table.getActualCellIndex(c)) {
                                                tdata.sorttype=Sort['"+type+"'];
                                        }
                                }
                        }
                } );
                if (args.col!=null) {
                        table.sort(t,args);
                }
        };

        /**
         * Add paging functionality to a table
         */
        table.autopage = function(t,args) {
                t = this.resolve(t,args);
                var tdata = this.tabledata[t.id];
                if (tdata.pagesize) {
                        this.processTableCells(t, "THEAD,TFOOT", function(c) {
                                var type = classValue(c,table.AutoPageJumpPrefix);
                                if (type=="next") { type = 1; }
                                else if (type=="previous") { type = -1; }
                                if (type!=null) {
                                        c.onclick = Function("","Table.pageJump(this,"+type+")");
                                }
                        } );
                        if (val = classValue(t,table.PageNumberPrefix)) {
                                tdata.container_number = document.getElementById(val);
                        }
                        if (val = classValue(t,table.PageCountPrefix)) {
                                tdata.container_count = document.getElementById(val);
                        }
                        return table.page(t,0,args);
                }
        };

        /**
         * A util function to cancel bubbling of clicks on filter dropdowns
         */
        table.cancelBubble = function(e) {
                e = e || window.event;
                if (typeof(e.stopPropagation)=="function") { e.stopPropagation(); }
                if (def(e.cancelBubble)) { e.cancelBubble = true; }
        };

        /**
         * Auto-filter a table
         */
        table.autofilter = function(t,args) {
                args = args || {};
                t = this.resolve(t,args);
                var tdata = this.tabledata[t.id],val;
                table.processTableCells(t, "THEAD", function(cell) {
                        if (hasClass(cell,table.FilterableClassName)) {
                                var cellIndex = table.getCellIndex(cell);
                                var colValues = table.getUniqueColValues(t,cellIndex);
                                if (colValues.length>0) {
                                        if (typeof(args.insert)=="function") {
                                                func.insert(cell,colValues);
                                        }
                                        else {
                                                var sel = '<select onchange="Table.filter(this,this)" onclick="Table.cancelBubble(event)" class="'+table.AutoFilterClassName+'"><option value="">'+table.FilterAllLabel+'</option>';
                                                for (var i=0; i<colValues.length; i++) {
                                                        sel += '<option value="'+colValues[i]+'">'+colValues[i]+'</option>';
                                                }
                                                sel += '</select>';
                                                cell.innerHTML += "<br>"+sel;
                                        }
                                }
                        }
                });
                if (val = classValue(t,table.FilteredRowcountPrefix)) {
                        tdata.container_filtered_count = document.getElementById(val);
                }
                if (val = classValue(t,table.RowcountPrefix)) {
                        tdata.container_all_count = document.getElementById(val);
                }
        };

        /**
         * Attach the auto event so it happens on load.
         * use jQuery's ready() function if available
         */
        if (typeof(jQuery)!="undefined") {
                jQuery(table.auto);
        }
        else if (window.addEventListener) {
                window.addEventListener( "load", table.auto, false );
        }
        else if (window.attachEvent) {
                window.attachEvent( "onload", table.auto );
        }

        return table;
})();
"""


maketree_js = """/**
 * Copyright (c)2005-2007 Matt Kruse (javascripttoolbox.com)
 *
 * Dual licensed under the MIT and GPL licenses.
 * This basically means you can use this code however you want for
 * free, but don't claim to have written it yourself!
 * Donations always accepted: http://www.JavascriptToolbox.com/donate/
 *
 * Please do not link to the .js files on javascripttoolbox.com from
 * your site. Copy the files locally to your server instead.
 *
 */
/*
This code is inspired by and extended from Stuart Langridge's aqlist code:
    http://www.kryogenix.org/code/browser/aqlists/
    Stuart Langridge, November 2002
    sil@kryogenix.org
    Inspired by Aaron's labels.js (http://youngpup.net/demos/labels/)
    and Dave Lindquist's menuDropDown.js (http://www.gazingus.org/dhtml/?id=109)
*/

// Automatically attach a listener to the window onload, to convert the trees
addEvent(window,"load",convertTrees);

// Utility function to add an event listener
function addEvent(o,e,f){
  if (o.addEventListener){ o.addEventListener(e,f,false); return true; }
  else if (o.attachEvent){ return o.attachEvent("on"+e,f); }
  else { return false; }
}

// utility function to set a global variable if it is not already set
function setDefault(name,val) {
  if (typeof(window[name])=="undefined" || window[name]==null) {
    window[name]=val;
  }
}

// Full expands a tree with a given ID
function expandTree(treeId) {
  var ul = document.getElementById(treeId);
  if (ul == null) { return false; }
  expandCollapseList(ul,nodeOpenClass);
}

// Fully collapses a tree with a given ID
function collapseTree(treeId) {
  var ul = document.getElementById(treeId);
  if (ul == null) { return false; }
  expandCollapseList(ul,nodeClosedClass);
}

// Expands enough nodes to expose an LI with a given ID
function expandToItem(treeId,itemId) {
  var ul = document.getElementById(treeId);
  if (ul == null) { return false; }
  var ret = expandCollapseList(ul,nodeOpenClass,itemId);
  if (ret) {
    var o = document.getElementById(itemId);
    if (o.scrollIntoView) {
      o.scrollIntoView(false);
    }
  }
}

// Performs 3 functions:
// a) Expand all nodes
// b) Collapse all nodes
// c) Expand all nodes to reach a certain ID
function expandCollapseList(ul,cName,itemId) {
  if (!ul.childNodes || ul.childNodes.length==0) { return false; }
  // Iterate LIs
  for (var itemi=0;itemi<ul.childNodes.length;itemi++) {
    var item = ul.childNodes[itemi];
    if (itemId!=null && item.id==itemId) { return true; }
    if (item.nodeName == "LI") {
      // Iterate things in this LI
      var subLists = false;
      for (var sitemi=0;sitemi<item.childNodes.length;sitemi++) {
        var sitem = item.childNodes[sitemi];
        if (sitem.nodeName=="UL") {
          subLists = true;
          var ret = expandCollapseList(sitem,cName,itemId);
          if (itemId!=null && ret) {
            item.className=cName;
            return true;
          }
        }
      }
      if (subLists && itemId==null) {
        item.className = cName;
      }
    }
  }
}

// Search the document for UL elements with the correct CLASS name, then process them
function convertTrees() {
  setDefault("treeClass","mktree");
  setDefault("nodeClosedClass","liClosed");
  setDefault("nodeOpenClass","liOpen");
  setDefault("nodeBulletClass","liBullet");
  setDefault("nodeLinkClass","bullet");
  setDefault("preProcessTrees",true);
  if (preProcessTrees) {
    if (!document.createElement) { return; } // Without createElement, we can't do anything
    var uls = document.getElementsByTagName("ul");
    if (uls==null) { return; }
    var uls_length = uls.length;
    for (var uli=0;uli<uls_length;uli++) {
      var ul=uls[uli];
      if (ul.nodeName=="UL" && ul.className==treeClass) {
        processList(ul);
      }
    }
  }
}

function treeNodeOnclick() {
  this.parentNode.className = (this.parentNode.className==nodeOpenClass) ? nodeClosedClass : nodeOpenClass;
  return false;
}
function retFalse() {
  return false;
}
// Process a UL tag and all its children, to convert to a tree
function processList(ul) {
  if (!ul.childNodes || ul.childNodes.length==0) { return; }
  // Iterate LIs
  var childNodesLength = ul.childNodes.length;
  for (var itemi=0;itemi<childNodesLength;itemi++) {
    var item = ul.childNodes[itemi];
    if (item.nodeName == "LI") {
      // Iterate things in this LI
      var subLists = false;
      var itemChildNodesLength = item.childNodes.length;
      for (var sitemi=0;sitemi<itemChildNodesLength;sitemi++) {
        var sitem = item.childNodes[sitemi];
        if (sitem.nodeName=="UL") {
          subLists = true;
          processList(sitem);
        }
      }
      var s= document.createElement("SPAN");
      var t= '\u00A0'; // &nbsp;
      s.className = nodeLinkClass;
      if (subLists) {
        // This LI has UL's in it, so it's a +/- node
        if (item.className==null || item.className=="") {
          item.className = nodeClosedClass;
        }
        // If it's just text, make the text work as the link also
        if (item.firstChild.nodeName=="#text") {
          t = t+item.firstChild.nodeValue;
          item.removeChild(item.firstChild);
        }
        s.onclick = treeNodeOnclick;
      }
      else {
        // No sublists, so it's just a bullet node
        item.className = nodeBulletClass;
        s.onclick = retFalse;
      }
      s.appendChild(document.createTextNode(t));
      item.insertBefore(s,item.firstChild);
    }
  }
}
"""




def make_html_file(metadata, results, tag, host, output_file_name, dirname):
    """
    Create HTML file contents for the job report, to stdout or filesystem.

    @param metadata: Dictionary with Job metadata (tests, exec time, etc).
    @param results: List with testcase results.
    @param tag: Job tag.
    @param host: Client hostname.
    @param output_file_name: Output file name. If empty string, prints to
            stdout.
    @param dirname: Prefix for HTML links. If empty string, the HTML links
            will be relative to the results dir.
    """
    html_prefix = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>Autotest job execution results</title>
<style type="text/css">
%s
</style>
<script type="text/javascript">
%s
%s
function popup(tag,text) {
var w = window.open('', tag, 'toolbar=no,location=no,directories=no,status=no,menubar=no,scrollbars=yes,resizable=yes, copyhistory=no,width=600,height=300,top=20,left=100');
w.document.open("text/html", "replace");
w.document.write(text);
w.document.close();
return true;
}
</script>
</head>
<body>
""" % (format_css, table_js, maketree_js)

    if output_file_name:
        output = open(output_file_name, "w")
    else:   #if no output file defined, print html file to console
        output = sys.stdout
    # create html page
    print >> output, html_prefix
    print >> output, '<h2 id=\"page_title\">Autotest job execution report</h2>'

    # formating date and time to print
    t = datetime.datetime.now()

    epoch_sec = time.mktime(t.timetuple())
    now = datetime.datetime.fromtimestamp(epoch_sec)

    # basic statistics
    total_executed = 0
    total_failed = 0
    total_passed = 0
    for res in results:
        if results[res][2] != None:
            total_executed += 1
            if results[res][2]['status'] == 'GOOD':
                total_passed += 1
            else:
                total_failed += 1
    stat_str = 'No test cases executed'
    if total_executed > 0:
        failed_perct = int(float(total_failed)/float(total_executed)*100)
        stat_str = ('From %d tests executed, %d have passed (%d%% failures)' %
                    (total_executed, total_passed, failed_perct))

    kvm_ver_str = metadata.get('kvmver', None)

    print >> output, '<table class="stats2">'
    print >> output, '<tr><td>HOST</td><td>:</td><td>%s</td></tr>' % host
    print >> output, '<tr><td>RESULTS DIR</td><td>:</td><td>%s</td></tr>'  % tag
    print >> output, '<tr><td>DATE</td><td>:</td><td>%s</td></tr>' % now.ctime()
    print >> output, '<tr><td>STATS</td><td>:</td><td>%s</td></tr>'% stat_str
    print >> output, '<tr><td></td><td></td><td></td></tr>'
    if kvm_ver_str is not None:
        print >> output, '<tr><td>KVM VERSION</td><td>:</td><td>%s</td></tr>' % kvm_ver_str
    print >> output, '</table>'

    ## print test results
    print >> output, '<br>'
    print >> output, '<h2 id=\"page_sub_title\">Test Results</h2>'
    print >> output, '<h2 id=\"comment\">click on table headers to asc/desc sort</h2>'
    result_table_prefix = """<table
id="t1" class="stats table-autosort:4 table-autofilter table-stripeclass:alternate table-page-number:t1page table-page-count:t1pages table-filtered-rowcount:t1filtercount table-rowcount:t1allcount">
<thead class="th table-sorted-asc table-sorted-desc">
<tr>
<th align="left" class="table-sortable:alphanumeric">Date/Time</th>
<th align="left" class="filterable table-sortable:alphanumeric">Test Case<br><input name="tc_filter" size="10" onkeyup="Table.filter(this,this)" onclick="Table.cancelBubble(event)"></th>
<th align="left" class="table-filterable table-sortable:alphanumeric">Status</th>
<th align="left">Time (sec)</th>
<th align="left">Info</th>
<th align="left">Debug</th>
</tr></thead>
<tbody>
"""
    print >> output, result_table_prefix
    def print_result(result, indent):
        while result != []:
            r = result.pop(0)
            res = results[r][2]
            print >> output, '<tr>'
            print >> output, '<td align="left">%s</td>' % res['time']
            print >> output, '<td align="left" style="padding-left:%dpx">%s</td>' % (indent * 20, res['title'])
            if res['status'] == 'GOOD':
                print >> output, '<td align=\"left\"><b><font color="#00CC00">PASS</font></b></td>'
            elif res['status'] == 'FAIL':
                print >> output, '<td align=\"left\"><b><font color="red">FAIL</font></b></td>'
            elif res['status'] == 'ERROR':
                print >> output, '<td align=\"left\"><b><font color="red">ERROR!</font></b></td>'
            else:
                print >> output, '<td align=\"left\">%s</td>' % res['status']
            # print exec time (seconds)
            print >> output, '<td align="left">%s</td>' % res['exec_time_sec']
            # print log only if test failed..
            if res['log']:
                #chop all '\n' from log text (to prevent html errors)
                rx1 = re.compile('(\s+)')
                log_text = rx1.sub(' ', res['log'])

                # allow only a-zA-Z0-9_ in html title name
                # (due to bug in MS-explorer)
                rx2 = re.compile('([^a-zA-Z_0-9])')
                updated_tag = rx2.sub('_', res['title'])

                html_body_text = '<html><head><title>%s</title></head><body>%s</body></html>' % (str(updated_tag), log_text)
                print >> output, '<td align=\"left\"><A HREF=\"#\" onClick=\"popup(\'%s\',\'%s\')\">Info</A></td>' % (str(updated_tag), str(html_body_text))
            else:
                print >> output, '<td align=\"left\"></td>'
            # print execution time
            print >> output, '<td align="left"><A HREF=\"%s\">Debug</A></td>' % os.path.join(dirname, res['subdir'], "debug")

            print >> output, '</tr>'
            print_result(results[r][1], indent + 1)

    print_result(results[""][1], 0)
    print >> output, "</tbody></table>"


    print >> output, '<h2 id=\"page_sub_title\">Host Info</h2>'
    print >> output, '<h2 id=\"comment\">click on each item to expend/collapse</h2>'
    ## Meta list comes here..
    print >> output, '<p>'
    print >> output, '<A href="#" class="button" onClick="expandTree(\'meta_tree\');return false;">Expand All</A>'
    print >> output, '&nbsp;&nbsp;&nbsp'
    print >> output, '<A class="button" href="#" onClick="collapseTree(\'meta_tree\'); return false;">Collapse All</A>'
    print >> output, '</p>'

    print >> output, '<ul class="mktree" id="meta_tree">'
    counter = 0
    keys = metadata.keys()
    keys.sort()
    for key in keys:
        val = metadata[key]
        print >> output, '<li id=\"meta_headline\">%s' % key
        print >> output, '<ul><table class="meta_table"><tr><td align="left">%s</td></tr></table></ul></li>' % val
    print >> output, '</ul>'

    print >> output, "</body></html>"
    if output_file_name:
        output.close()


def parse_result(dirname, line, results_data):
    """
    Parse job status log line.

    @param dirname: Job results dir
    @param line: Status log line.
    @param results_data: Dictionary with for results.
    """
    parts = line.split()
    if len(parts) < 4:
        return None
    global tests
    if parts[0] == 'START':
        pair = parts[3].split('=')
        stime = int(pair[1])
        results_data[parts[1]] = [stime, [], None]
        try:
            parent_test = re.findall(r".*/", parts[1])[0][:-1]
            results_data[parent_test][1].append(parts[1])
        except IndexError:
            results_data[""][1].append(parts[1])

    elif (parts[0] == 'END'):
        result = {}
        exec_time = ''
        # fetch time stamp
        if len(parts) > 7:
            temp = parts[5].split('=')
            exec_time = temp[1] + ' ' + parts[6] + ' ' + parts[7]
        # assign default values
        result['time'] = exec_time
        result['testcase'] = 'na'
        result['status'] = 'na'
        result['log'] = None
        result['exec_time_sec'] = 'na'
        tag = parts[3]

        result['subdir'] = parts[2]
        # assign actual values
        rx = re.compile('^(\w+)\.(.*)$')
        m1 = rx.findall(parts[3])
        if len(m1):
            result['testcase'] = m1[0][1]
        else:
            result['testcase'] = parts[3]
        result['title'] = str(tag)
        result['status'] = parts[1]
        if result['status'] != 'GOOD':
            result['log'] = get_exec_log(dirname, tag)
        if len(results_data)>0:
            pair = parts[4].split('=')
            etime = int(pair[1])
            stime = results_data[parts[2]][0]
            total_exec_time_sec = etime - stime
            result['exec_time_sec'] = total_exec_time_sec
        results_data[parts[2]][2] = result
    return None


def get_exec_log(resdir, tag):
    """
    Get job execution summary.

    @param resdir: Job results dir.
    @param tag: Job tag.
    """
    stdout_file = os.path.join(resdir, tag, 'debug', 'stdout')
    stderr_file = os.path.join(resdir, tag, 'debug', 'stderr')
    status_file = os.path.join(resdir, tag, 'status')
    dmesg_file = os.path.join(resdir, tag, 'sysinfo', 'dmesg')
    log = ''
    log += '<br><b>STDERR:</b><br>'
    log += get_info_file(stderr_file)
    log += '<br><b>STDOUT:</b><br>'
    log += get_info_file(stdout_file)
    log += '<br><b>STATUS:</b><br>'
    log += get_info_file(status_file)
    log += '<br><b>DMESG:</b><br>'
    log += get_info_file(dmesg_file)
    return log


def get_info_file(filename):
    """
    Gets the contents of an autotest info file.

    It also and highlights the file contents with possible problems.

    @param filename: Info file path.
    """
    data = ''
    errors = re.compile(r"\b(error|fail|failed)\b", re.IGNORECASE)
    if os.path.isfile(filename):
        f = open('%s' % filename, "r")
        lines = f.readlines()
        f.close()
        rx = re.compile('(\'|\")')
        for line in lines:
            new_line = rx.sub('', line)
            errors_found = errors.findall(new_line)
            if len(errors_found) > 0:
                data += '<font color=red>%s</font><br>' % str(new_line)
            else:
                data += '%s<br>' % str(new_line)
        if not data:
            data = 'No Information Found.<br>'
    else:
        data = 'File not found.<br>'
    return data


def usage():
    """
    Print stand alone program usage.
    """
    print 'usage:',
    print 'make_html_report.py -r <result_directory> [-f output_file] [-R]'
    print '(e.g. make_html_reporter.py -r '\
          '/usr/local/autotest/client/results/default -f /tmp/myreport.html)'
    print 'add "-R" for an html report with relative-paths (relative '\
          'to results directory)'
    print ''
    sys.exit(1)


def get_keyval_value(result_dir, key):
    """
    Return the value of the first appearance of key in any keyval file in
    result_dir. If no appropriate line is found, return 'Unknown'.

    @param result_dir: Path that holds the keyval files.
    @param key: Specific key we're retrieving.
    """
    keyval_pattern = os.path.join(result_dir, "kvm.*", "keyval")
    keyval_lines = commands.getoutput(r"grep -h '\b%s\b.*=' %s"
                                      % (key, keyval_pattern))
    if not keyval_lines:
        return "Unknown"
    keyval_line = keyval_lines.splitlines()[0]
    if key in keyval_line and "=" in keyval_line:
        return keyval_line.split("=")[1].strip()
    else:
        return "Unknown"


def get_kvm_version(result_dir):
    """
    Return an HTML string describing the KVM version.

    @param result_dir: An Autotest job result dir.
    """
    kvm_version = get_keyval_value(result_dir, "kvm_version")
    kvm_userspace_version = get_keyval_value(result_dir,
                                             "kvm_userspace_version")
    if kvm_version == "Unknown" or kvm_userspace_version == "Unknown":
        return None
    return "Kernel: %s<br>Userspace: %s" % (kvm_version, kvm_userspace_version)


def create_report(dirname, html_path='', output_file_name=None):
    """
    Create an HTML report with info about an autotest client job.

    If no relative path (html_path) or output file name provided, an HTML
    file in the toplevel job results dir called 'job_report.html' will be
    created, with relative links.

    @param html_path: Prefix for the HTML links. Useful to specify absolute
            in the report (not wanted most of the time).
    @param output_file_name: Path to the report file.
    """
    res_dir = os.path.abspath(dirname)
    tag = res_dir
    status_file_name = os.path.join(dirname, 'status')
    sysinfo_dir = os.path.join(dirname, 'sysinfo')
    host = get_info_file(os.path.join(sysinfo_dir, 'hostname'))
    rx = re.compile('^\s+[END|START].*$')
    # create the results set dict
    results_data = {}
    results_data[""] = [0, [], None]
    if os.path.exists(status_file_name):
        f = open(status_file_name, "r")
        lines = f.readlines()
        f.close()
        for line in lines:
            if rx.match(line):
                parse_result(dirname, line, results_data)
    # create the meta info dict
    metalist = {
                'uname': get_info_file(os.path.join(sysinfo_dir, 'uname')),
                'cpuinfo':get_info_file(os.path.join(sysinfo_dir, 'cpuinfo')),
                'meminfo':get_info_file(os.path.join(sysinfo_dir, 'meminfo')),
                'df':get_info_file(os.path.join(sysinfo_dir, 'df')),
                'modules':get_info_file(os.path.join(sysinfo_dir, 'modules')),
                'gcc':get_info_file(os.path.join(sysinfo_dir, 'gcc_--version')),
                'dmidecode':get_info_file(os.path.join(sysinfo_dir, 'dmidecode')),
                'dmesg':get_info_file(os.path.join(sysinfo_dir, 'dmesg')),
    }
    if get_kvm_version(dirname) is not None:
        metalist['kvm_ver'] = get_kvm_version(dirname)

    if output_file_name is None:
        output_file_name = os.path.join(dirname, 'job_report.html')
    make_html_file(metalist, results_data, tag, host, output_file_name,
                   html_path)


def main(argv):
    """
    Parses the arguments and executes the stand alone program.
    """
    dirname = None
    output_file_name = None
    relative_path = False
    try:
        opts, args = getopt.getopt(argv, "r:f:h:R", ['help'])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt == '-r':
            dirname =  arg
        elif opt == '-f':
            output_file_name =  arg
        elif opt == '-R':
            relative_path = True
        else:
            usage()
            sys.exit(1)

    html_path = dirname
    # don't use absolute path in html output if relative flag passed
    if relative_path:
        html_path = ''

    if dirname:
        if os.path.isdir(dirname): # TBD: replace it with a validation of
                                   # autotest result dir
            create_report(dirname, html_path, output_file_name)
            sys.exit(0)
        else:
            print 'Invalid result directory <%s>' % dirname
            sys.exit(1)
    else:
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
