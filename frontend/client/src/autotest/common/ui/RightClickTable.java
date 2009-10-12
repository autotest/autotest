package autotest.common.ui;

import com.google.gwt.event.dom.client.ContextMenuEvent;
import com.google.gwt.event.dom.client.ContextMenuHandler;
import com.google.gwt.event.dom.client.DomEvent;
import com.google.gwt.event.dom.client.HasContextMenuHandlers;
import com.google.gwt.event.shared.HandlerRegistration;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Element;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HTMLTable;

public class RightClickTable extends FlexTable
        implements ContextMenuHandler, HasContextMenuHandlers {
    
    protected static class RowColumn {
        int row;
        int column;
        
        public RowColumn(int row, int column) {
            this.row = row;
            this.column = column;
        }
    }
    
    private boolean hasHandler;
    
    @Override
    public HandlerRegistration addContextMenuHandler(ContextMenuHandler handler) {
        if (!hasHandler) {
            addDomHandler(this, ContextMenuEvent.getType());
            hasHandler = true;
        }
        return addDomHandler(handler, ContextMenuEvent.getType());
    }
    
    @Override
    public void onContextMenu(ContextMenuEvent event) {
        event.preventDefault();
    }
    
    public HTMLTable.Cell getCellForDomEvent(DomEvent<?> event) {
        // This is copied from HTMLTable.getCellForEvent().
        final Element td = getEventTargetCell(Event.as(event.getNativeEvent()));
        if (td == null) {
            return null;
        }
        
        RowColumn position = getCellPosition(td);
        
        return new HTMLTable.Cell(position.row, position.column) {
            @Override
            public Element getElement() {
                return td;
            }
        };
    }
    
    protected RowColumn getCellPosition(Element td) {
        Element tr = DOM.getParent(td);
        Element body = DOM.getParent(tr);
        int row = DOM.getChildIndex(body, tr);
        int column = DOM.getChildIndex(tr, td);
        return new RowColumn(row, column);
    }
}
