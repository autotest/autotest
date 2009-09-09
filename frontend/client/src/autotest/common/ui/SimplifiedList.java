// Copyright 2009 Google Inc. All Rights Reserved.

package autotest.common.ui;

import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.shared.HandlerRegistration;

public interface SimplifiedList {
    public void clear();
    public void addItem(String name, String value);
    public String getSelectedName();
    public void selectByName(String name);
    public HandlerRegistration addChangeHandler(ChangeHandler handler);
}
