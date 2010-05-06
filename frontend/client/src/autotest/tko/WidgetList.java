package autotest.tko;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;


class WidgetList<T extends Widget> extends Composite implements ClickHandler {
    public interface ListWidgetFactory<S extends Widget> {
        public List<String> getWidgetTypes();
        public S getNewWidget(String type);
    }

    private ListWidgetFactory<T> factory;
    private List<T> widgets = new ArrayList<T>();
    private Panel widgetPanel = new VerticalPanel();
    private HorizontalPanel addLinksPanel = new HorizontalPanel();

    public WidgetList(ListWidgetFactory<T> factory) {
        this.factory = factory;

        addLinksPanel.setSpacing(10);
        for (String type : factory.getWidgetTypes()) {
            Anchor addLink = new Anchor(type);
            addLink.addClickHandler(this);
            addLinksPanel.add(addLink);
        }

        Panel outerPanel = new VerticalPanel();
        outerPanel.add(widgetPanel);
        outerPanel.add(addLinksPanel);
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

    public void onClick(ClickEvent event) {
        assert (event.getSource() instanceof Anchor);

        Anchor addLink = (Anchor) event.getSource();
        T widget = factory.getNewWidget(addLink.getText());
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
