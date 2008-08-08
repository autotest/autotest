package autotest.common.ui;

import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.ClickListenerCollection;
import com.google.gwt.user.client.ui.Hyperlink;

/**
 * Hyperlink widget that doesn't mess with browser history.  Most of this code
 * is copied from gwt.user.client.ui.Hyperlink; unfortunately, due to the way 
 * that class is built, we can't get rid of it.
 *
 */
public class SimpleHyperlink extends Hyperlink {
    private ClickListenerCollection clickListeners;
    
    public SimpleHyperlink(String text) {
        super(text, "");
        setStyleName("SimpleHyperlink");
    }

    @Override
    public void onBrowserEvent(Event event) {
        if (DOM.eventGetType(event) == Event.ONCLICK) {
            if (clickListeners != null) {
                clickListeners.fireClick(this);
            }
            DOM.eventPreventDefault(event);
        }
    }

    @Override
    public void addClickListener(ClickListener listener) {
        if (clickListeners == null) {
            clickListeners = new ClickListenerCollection();
        }
        clickListeners.add(listener);
    }

    @Override
    public void removeClickListener(ClickListener listener) {
        if (clickListeners != null) {
            clickListeners.remove(listener);
        }
    }
}
