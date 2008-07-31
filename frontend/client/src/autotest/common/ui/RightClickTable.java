package autotest.common.ui;

import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Element;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.TableListener;
import com.google.gwt.user.client.ui.TableListenerCollection;

/**
 * This is basically a hack to support browser contextmenu (right-click) events, until GWT supports
 * them directly.
 */
public class RightClickTable extends FlexTable {
    protected static class RowColumn {
        int row;
        int column;
        
        public RowColumn(int row, int column) {
            this.row = row;
            this.column = column;
        }
    }
    
    // need to keep our own copy of the listener set since the superclass set isn't visible
    protected TableListenerCollection listeners = new TableListenerCollection();
    
    public void sinkRightClickEvents() {
        setOnContextMenu(getElement());
    }
    
    @Override
    public void addTableListener(TableListener listener) {
        super.addTableListener(listener);
        listeners.add(listener);
    }
    
    @Override
    public void removeTableListener(TableListener listener) {
        super.removeTableListener(listener);
        listeners.remove(listener);
    }
    
    public static boolean isRightClick(Event event) {
        return event.getType().equals("contextmenu");
    }

    @Override
    public void onBrowserEvent(Event event) {
        if (event.getType().equals("click") || isRightClick(event)) {
            if (isRightClick(event)) {
                event.preventDefault();
            }
            
            // Find out which cell was actually clicked.
            Element td = getEventTargetCell(event);
            if (td == null) {
              return;
            }
            
            RowColumn position = getCellPosition(td);
            listeners.fireCellClicked(this, position.row, position.column);
        }
    }
    
    protected RowColumn getCellPosition(Element td) {
        // This is copied from HTMLTable.onBrowserEvent().
        Element tr = DOM.getParent(td);
        Element body = DOM.getParent(tr);
        int row = DOM.getChildIndex(body, tr);
        int column = DOM.getChildIndex(tr, td);
        return new RowColumn(row, column);
    }
    
    private native void setOnContextMenu(Element elem) /*-{
        elem.oncontextmenu = @com.google.gwt.user.client.impl.DOMImplStandard::dispatchEvent;
    }-*/;
}
