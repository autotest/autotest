package autotest.tko;

import autotest.common.ui.SimpleHyperlink;

import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

class WidgetList<T extends Widget> extends Composite implements ClickListener {
    public interface ListWidgetFactory<S extends Widget> {
        public S getNewWidget();
    }
    
    private ListWidgetFactory<T> factory;
    private List<T> widgets = new ArrayList<T>();
    private Panel widgetPanel = new VerticalPanel();
    private SimpleHyperlink addLink;
    
    public WidgetList(ListWidgetFactory<T> factory, String addText) {
        this.factory = factory;
        
        addLink = new SimpleHyperlink(addText);
        addLink.addClickListener(this);
        
        Panel outerPanel = new VerticalPanel();
        outerPanel.add(widgetPanel);
        outerPanel.add(addLink);
        initWidget(outerPanel);
    }
    
    public void addWidget(T widget) {
        widgets.add(widget);
        widgetPanel.add(widget);
    }

    public void deleteWidget(T widget) {
        widgets.remove(widget);
        widgetPanel.remove(widget);
    }

    public void onClick(Widget sender) {
        assert sender == addLink;
        T widget = factory.getNewWidget();
        addWidget(widget);
    }
    
    public List<T> getWidgets() {
        return Collections.unmodifiableList(widgets);
    }

    public void clear() {
        widgets.clear();
        widgetPanel.clear();
    }
}
