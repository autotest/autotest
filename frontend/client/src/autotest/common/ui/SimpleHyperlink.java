package autotest.common.ui;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.DomEvent;
import com.google.gwt.event.shared.HandlerRegistration;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.Hyperlink;

/**
 * Hyperlink widget that doesn't mess with browser history.  Most of this code
 * is copied from gwt.user.client.ui.Hyperlink; unfortunately, due to the way 
 * that class is built, we can't get rid of it.
 *
 */
public class SimpleHyperlink extends Hyperlink {
    public SimpleHyperlink(String text, boolean asHtml) {
        super(text, asHtml, "");
        setStyle();
    }

    public SimpleHyperlink(String text) {
        super(text, "");
        setStyle();
    }
    
    private void setStyle() {
        setStyleName("SimpleHyperlink");        
    }
    
    @Override
    public void onBrowserEvent(Event event) {
        if (DOM.eventGetType(event) == Event.ONCLICK) {
            DomEvent.fireNativeEvent(event, this);
            DOM.eventPreventDefault(event);
        }
    }

    @Override
    public HandlerRegistration addClickHandler(ClickHandler handler) {
        return addDomHandler(handler, ClickEvent.getType());
    }
}
