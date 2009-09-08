package autotest.common.ui;

import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.shared.HandlerRegistration;

public interface ToggleControl extends HasClickHandlers {
    public boolean isActive();
    public void setActive(boolean active);
    public HandlerRegistration addClickHandler(ClickHandler handler);
}
