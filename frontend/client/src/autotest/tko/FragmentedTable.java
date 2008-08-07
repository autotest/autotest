package autotest.tko;

import autotest.common.ui.RightClickTable;

import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Element;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.HTMLTable;

import java.util.ArrayList;
import java.util.List;

/**
 * Customized table class supporting multiple tbody elements.  It is modified to support input
 * handling, getRowCount(), getCellCount(), and getCellFormatter().getElement().  getElement() 
 * also works.  Calls to other methods aren't guaranteed to work.
 */
class FragmentedTable extends RightClickTable {
    public class FragmentedCellFormatter extends HTMLTable.CellFormatter {
        @Override
        public Element getElement(int row, int column) {
            checkCellBounds(row, column);
            Element bodyElem = bodyElems.get(getFragmentIndex(row));
            return getCellElement(bodyElem, getRowWithinFragment(row), column);
        }
        
        /**
         * Native method to efficiently get a td element from a tbody. Copied from GWT's 
         * HTMLTable.java. 
         */
        private native Element getCellElement(Element tbody, int row, int col) /*-{
            return tbody.rows[row].cells[col];
        }-*/;
    }
    
    private List<Element> bodyElems = new ArrayList<Element>();
    private int totalRowCount;
    private int rowsPerFragment;
    
    public FragmentedTable() {
        super();
        setCellFormatter(new FragmentedCellFormatter());
    }
    
    /**
     * This method must be called after added or removing tbody elements and before using other
     * functionality (accessing cell elements, input handling, etc.).
     */
    public void updateBodyElems() {
        totalRowCount = 0;
        Element tbody = DOM.getFirstChild(getElement());
        for(; tbody != null; tbody = DOM.getNextSibling(tbody)) {
            assert tbody.getTagName().equalsIgnoreCase("tbody");
            bodyElems.add(tbody);
            totalRowCount += getRowCount(tbody);
        }
    }

    public void reset() {
        bodyElems.clear();
        TkoUtils.clearDomChildren(getElement());
    }

    private int getRowWithinFragment(int row) {
        return row % rowsPerFragment;
    }

    private int getFragmentIndex(int row) {
        return row / rowsPerFragment;
    }

    @Override
    protected RowColumn getCellPosition(Element td) {
        Element tr = DOM.getParent(td);
        Element body = DOM.getParent(tr);
        int fragmentIndex = DOM.getChildIndex(getElement(), body);
        int rowWithinFragment = DOM.getChildIndex(body, tr);
        int row = fragmentIndex * rowsPerFragment + rowWithinFragment;
        int column = DOM.getChildIndex(tr, td);
        return new RowColumn(row, column);
    }

    /**
     * This is a modified version of getEventTargetCell() from HTMLTable.java.
     */
    @Override
    protected Element getEventTargetCell(Event event) {
        Element td = DOM.eventGetTarget(event);
        for (; td != null; td = DOM.getParent(td)) {
            // If it's a TD, it might be the one we're looking for.
            if (DOM.getElementProperty(td, "tagName").equalsIgnoreCase("td")) {
                // Make sure it's directly a part of this table before returning
                // it.
                Element tr = DOM.getParent(td);
                Element body = DOM.getParent(tr);
                Element tableElem = DOM.getParent(body);
                if (tableElem == getElement()) {
                    return td;
                }
            }
            // If we run into this table's element, we're out of options.
            if (td == getElement()) {
                return null;
            }
        }
        return null;
    }

    @Override
    public int getCellCount(int row) {
        Element bodyElem = bodyElems.get(getFragmentIndex(row));
        return getCellCount(bodyElem, getRowWithinFragment(row));
    }

    @Override
    public int getRowCount() {
        return totalRowCount;
    }
    
    private native int getRowCount(Element tbody) /*-{
        return tbody.rows.length;
    }-*/;

    private native int getCellCount(Element tbody, int row) /*-{
        return tbody.rows[row].cells.length;
    }-*/;

    /**
     * This must be called before using other functionality (accessing cell elements, input 
     * handling, etc.).
     * @param rowsPerFragment  The number of rows in each tbody.  The last tbody may have fewer 
     * rows.  All others must have exactly this number of rows.
     */
    public void setRowsPerFragment(int rowsPerFragment) {
        this.rowsPerFragment = rowsPerFragment;
    }
}
