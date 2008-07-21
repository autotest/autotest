package autotest.common.ui;

import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Element;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.TableListener;

import java.util.HashSet;
import java.util.Set;

/**
 * This is basically a hack to support browser contextmenu (right-click) events, until GWT supports
 * them directly.
 */
public class RightClickTable extends FlexTable {
    private static Event currentRightClickEvent = null;
    
    // need to keep our own copy of the listener set since the superclass set isn't visible
    private Set<TableListener> listeners = new HashSet<TableListener>();
    
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
    
    private void fireRightClick(int row, int column) {
        for (TableListener listener : listeners) {
            listener.onCellClicked(this, row, column);
        }
    }
    
    public static boolean isRightClick(Event event) {
        return event == currentRightClickEvent;
    }

    @Override
    public void onBrowserEvent(Event event) {
        if (event.getType().equals("contextmenu")) {
            currentRightClickEvent = event;
            event.preventDefault();
            handleRightClick(event);
        } else {
            super.onBrowserEvent(event);
        }
    }
    
    private void handleRightClick(Event event) {
        // This is copied from HTMLTable.onBrowserEvent().
        
        // Find out which cell was actually clicked.
        Element td = getEventTargetCell(event);
        if (td == null) {
          return;
        }
        Element tr = DOM.getParent(td);
        Element body = DOM.getParent(tr);
        int row = DOM.getChildIndex(body, tr);
        int column = DOM.getChildIndex(tr, td);
        // Fire the event.
        fireRightClick(row, column);
    }
    
    private native void setOnContextMenu(Element elem) /*-{
        elem.oncontextmenu = @com.google.gwt.user.client.impl.DOMImplStandard::dispatchEvent;
    }-*/;
}
