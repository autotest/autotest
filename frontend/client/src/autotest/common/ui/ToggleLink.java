package autotest.common.ui;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.DomEvent;
import com.google.gwt.event.shared.HandlerRegistration;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Composite;

public class ToggleLink extends Composite implements ClickHandler, ToggleControl {
    private String activateText;
    private String deactivateText;
    private Anchor link;

    public ToggleLink(String activateText, String deactivateText) {
        this.activateText = activateText;
        this.deactivateText = deactivateText;

        link = new Anchor(activateText);
        link.addClickHandler(this);
        initWidget(link);
    }

    public boolean isActive() {
        return link.getText().equals(deactivateText);
    }

    public void setActive(boolean active) {
        link.setText(active ? deactivateText : activateText);
    }

    @Override
    public HandlerRegistration addClickHandler(ClickHandler handler) {
        return addHandler(handler, ClickEvent.getType());
    }

    @Override
    public void onClick(ClickEvent event) {
        setActive(!isActive());
        // re-fire the event with this as the source
        DomEvent.fireNativeEvent(Event.getCurrentEvent(), this);
    }
}
