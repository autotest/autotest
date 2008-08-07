package autotest.tko;

import autotest.tko.Spreadsheet.CellInfo;

import com.google.gwt.core.client.GWT;
import com.google.gwt.dom.client.Element;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.ui.HTMLTable;


public class TableRenderer {
    // min-width/min-height aren't supported in the hosted mode browser
    public static final String SIZE_PREFIX = GWT.isScript() ? "min-" : "";
    private static final String NONCLICKABLE_CLASS = "spreadsheet-cell-nonclickable";
    
    protected String attributeString(String attribute, String value) {
        if (value.equals(""))
            return "";
        return " " + attribute + "=\"" + value + "\"";
    }
    
    public void renderRowsAndAppend(HTMLTable tableObject, CellInfo[][] rows, 
                                    int startRow, int maxRows, boolean renderNull) {
        StringBuffer htmlBuffer= new StringBuffer();
        htmlBuffer.append("<table><tbody>");
        for (int rowIndex = startRow; rowIndex < startRow + maxRows && rowIndex < rows.length;
             rowIndex++) {
            CellInfo[] row = rows[rowIndex];
            htmlBuffer.append("<tr>");
            for (CellInfo cell : row) {
                if (cell == null && renderNull) {
                    htmlBuffer.append("<td> </td>");
                } else if (cell != null) {
                    String tdAttributes = "", divAttributes = "", divStyle = "";
                    if (cell.color != null) {
                        tdAttributes += attributeString("style", 
                                                       "background-color: " + cell.color + ";");
                    }
                    if (cell.rowSpan > 1) {
                        tdAttributes += attributeString("rowspan", Integer.toString(cell.rowSpan)); 
                    }
                    if (cell.colSpan > 1) {
                        tdAttributes += attributeString("colspan", Integer.toString(cell.colSpan)); 
                    }
                    
                    if (cell.widthPx != null) {
                        divStyle += SIZE_PREFIX + "width: " + cell.widthPx + "px; ";
                    }
                    if (cell.heightPx != null) {
                        divStyle += SIZE_PREFIX + "height: " + cell.heightPx + "px; ";
                    }
                    if (!divStyle.equals("")) {
                        divAttributes += attributeString("style", divStyle);
                    }
                    if (cell.isEmpty()) {
                        divAttributes += attributeString("class", NONCLICKABLE_CLASS);
                    }
                    
                    htmlBuffer.append("<td " + tdAttributes + ">");
                    htmlBuffer.append("<div " + divAttributes + ">");
                    htmlBuffer.append(cell.contents);
                    htmlBuffer.append("</div></td>");
                }
            }
            htmlBuffer.append("</tr>");
        }
        htmlBuffer.append("</tbody></table>");
        
        renderBody(tableObject, htmlBuffer.toString());
    }
    
    public void renderRows(HTMLTable tableObject, CellInfo[][] rows, boolean renderNull) {
        TkoUtils.clearDomChildren(tableObject.getElement()); // remove existing tbodies
        renderRowsAndAppend(tableObject, rows, 0, rows.length, renderNull);
    }
    
    public void renderRows(HTMLTable tableObject, CellInfo[][] rows) {
        renderRows(tableObject, rows, true);
    }

    private void renderBody(HTMLTable tableObject, String html) {
        // render the table within a DIV
        Element tempDiv = DOM.createDiv();
        tempDiv.setInnerHTML(html);
        
        // inject the new tbody into the existing table
        Element newTable = tempDiv.getFirstChildElement();
        Element newBody = newTable.getFirstChildElement();
        tableObject.getElement().appendChild(newBody);
        
        setBodyElement(tableObject, newBody);
    }
    
    /**
     * A little hack to set the private member variable bodyElem of an HTMLTable.
     */
    protected native void setBodyElement(HTMLTable table, Element newBody) /*-{
        table.@com.google.gwt.user.client.ui.HTMLTable::bodyElem = newBody;
    }-*/;

}
